"""Authenticated feedback, bounded multipart ingress and private image delivery."""
from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import threading
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser

from app.config import settings
from app.database import get_db
from app.models import User
from app.routers.auth import get_current_user
from app.schemas.feedback import FeedbackCreate, FeedbackResponse, FeedbackSubmissionStatus
from app.services import feedback_submission_service as submissions, filing_list_service
from app.services.feedback_image_service import (
    FeedbackImageBusy, FeedbackImageError, FeedbackImageTimeout, normalize_feedback_image,
)
from app.services.feedback_storage_service import FeedbackStorageError
from app.services.feedback_storage_worker_service import run_feedback_storage_operation
from app.services.posthog_client import capture_event
from app.services.rate_limiter import RateLimiter, enforce_rate_limit, get_client_ip
from app.services.request_work import request_work_scope, run_owned_sync
from app.services.resend_service import send_email

router = APIRouter()
logger = logging.getLogger(__name__)
_IP_HASH_SALT = settings.IP_HASH_SALT or settings.SECRET_KEY
FEEDBACK_LIMITER = RateLimiter(limit=10, window_seconds=3600)
# A separate byte-admission budget: replays are not new reports, but they must not parse
# unlimited multipart bodies. The SQL allowance independently bounds new reports fleet-wide.
MEDIA_INGRESS_LIMITER = RateLimiter(limit=60, window_seconds=3600)
FEEDBACK_RATE_LIMIT_DETAIL = "You've sent a lot of feedback in the last hour. Try again a little later."
MAX_FILES = 3
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_BODY_BYTES = 16 * 1024 * 1024
_TYPES = ("image/png", "image/jpeg", "image/webp")
_UPLOAD_SLOTS = threading.BoundedSemaphore(2)
_PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}


def _hash_ip(ip: str) -> str:
    return hashlib.sha256(f"{ip}{_IP_HASH_SALT}".encode("utf-8")).hexdigest()


def _client_ip(request: Request) -> str:
    return get_client_ip(request)


def _db_unit(db: Session, operation, *args):
    try:
        return operation(db, *args)
    finally:
        filing_list_service.release_request_session(db)


def _key(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        return str(UUID(raw))
    except (ValueError, AttributeError):
        raise HTTPException(422, "Use a valid submission identifier.") from None


def _check_reader(request: Request, user_id: int, *, required: bool = False) -> None:
    expected = request.headers.get("x-feedback-user-id")
    if (required or expected is not None) and expected != str(user_id):
        raise HTTPException(409, "Your account changed. Reopen feedback before sending.")


def _error(exc: submissions.FeedbackSubmissionError) -> HTTPException:
    outcomes = {
        "owner_missing": (401, "Your session has ended. Log in again before sending feedback."),
        "not_found": (404, "Feedback submission not found."),
        "gone": (410, "This screenshot is no longer available."),
        "key_conflict": (409, "This submission identifier belongs to a different draft."),
        "stale_attempt": (409, "This attempt has ended. Check its receipt before retrying."),
        "incomplete_upload": (503, "Screenshots could not be saved. Your draft is ready to retry."),
        "quota": (429, FEEDBACK_RATE_LIMIT_DETAIL),
        "retry_limit": (429, "This draft has reached its retry limit. Check its receipt, then start a new report."),
    }
    code, detail = outcomes.get(exc.code, (503, "Feedback is temporarily unavailable. Please try again."))
    return HTTPException(code, detail, headers={**_PRIVATE_HEADERS, **({"Retry-After": "3600"} if code == 429 else {})})


def _claim_response(claim: submissions.SubmissionClaim) -> JSONResponse:
    if claim.receipt.state == "submitted":
        return JSONResponse(claim.receipt.feedback.model_dump(mode="json"), headers=_PRIVATE_HEADERS)
    return JSONResponse(claim.receipt.model_dump(mode="json"), status_code=202, headers={
        **_PRIVATE_HEADERS, "Retry-After": str(claim.receipt.retry_after_seconds or 1),
    })


async def _after_saved(user_id: int, user_email: str | None, saved: FeedbackResponse,
                       payload: FeedbackCreate, attachment_count: int = 0) -> None:
    try:
        capture_event(str(user_id), "feedback_submitted", {"type": saved.type, "attachment_count": attachment_count})
    except Exception:
        pass
    try:
        await _notify_admin(user_id, user_email, saved.id, payload, attachment_count)
    except Exception:
        logger.warning("Feedback notification unavailable")


@router.get("/capabilities")
async def feedback_capabilities(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    async with request_work_scope():
        await run_owned_sync(filing_list_service.release_request_session, db)
    return JSONResponse({
        "attachments_enabled": bool(settings.FEEDBACK_MEDIA_ENABLED and settings.FEEDBACK_MEDIA_BUCKET),
        "max_files": MAX_FILES, "max_file_bytes": MAX_FILE_BYTES, "max_total_bytes": MAX_BODY_BYTES,
        "accepted_content_types": list(_TYPES),
    }, headers=_PRIVATE_HEADERS)


@router.post("/", response_model=FeedbackResponse | FeedbackSubmissionStatus, status_code=201)
async def submit_feedback(payload: FeedbackCreate, request: Request, response: Response,
                          current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id, email = current_user.id, current_user.email
    _check_reader(request, user_id)
    submission_key = _key(request.headers.get("idempotency-key"))
    ip_hash = _hash_ip(_client_ip(request))
    claim = None
    try:
        async with request_work_scope():
            if submission_key:
                claim = await run_owned_sync(_db_unit, db, submissions.claim_submission, user_id,
                                             submission_key, submissions.payload_fingerprint(payload, []))
                if claim.attempt_token is None:
                    return _claim_response(claim)
                saved = await run_owned_sync(_db_unit, db, submissions.publish_submission, user_id,
                                             claim, payload, ip_hash, {}, settings.FEEDBACK_MEDIA_RETENTION_DAYS)
            else:
                enforce_rate_limit(request, FEEDBACK_LIMITER, f"feedback:{user_id}",
                                   include_client_ip=False, error_detail=FEEDBACK_RATE_LIMIT_DETAIL)
                saved = await run_owned_sync(_db_unit, db, submissions.persist_legacy_feedback,
                                             user_id, payload, ip_hash)
        response.headers.update(_PRIVATE_HEADERS)
        await _after_saved(user_id, email, saved, payload)
        return saved
    except submissions.FeedbackSubmissionError as exc:
        raise _error(exc) from None
    finally:
        if claim is not None and claim.attempt_token is not None:
            # Published attempts are untouched; an exception before commit becomes retryable.
            # Compensation owns its SQL worker too, including further cancellation.
            with anyio.CancelScope(shield=True):
                async with request_work_scope():
                    await run_owned_sync(_db_unit, db, submissions.fail_attempt, user_id, claim)


class _FeedbackMultipartParser(MultiPartParser):
    """Bound file bytes and headers while parsing, before temporary storage grows."""

    def on_part_begin(self):
        super().on_part_begin()
        self._feedback_file_bytes = 0
        self._feedback_header_bytes = 0

    def on_header_field(self, data, start, end):
        self._count_header(end - start)
        super().on_header_field(data, start, end)

    def on_header_value(self, data, start, end):
        self._count_header(end - start)
        super().on_header_value(data, start, end)

    def _count_header(self, size):
        self._feedback_header_bytes += size
        if self._feedback_header_bytes > 4096:
            raise MultiPartException("Screenshot metadata is too large.")

    def on_part_data(self, data, start, end):
        if self._current_part.file is not None:
            self._feedback_file_bytes += end - start
            if self._feedback_file_bytes > MAX_FILE_BYTES:
                raise MultiPartException("Each screenshot must be no larger than 5 MiB.")
        super().on_part_data(data, start, end)


async def _read_upload(request: Request) -> tuple[FeedbackCreate, list[bytes]]:
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "multipart/form-data":
        raise HTTPException(415, "Send screenshots as multipart form data.")
    length = request.headers.get("content-length")
    if length is not None:
        try:
            if int(length) < 0 or int(length) > MAX_BODY_BYTES:
                raise HTTPException(413, "Screenshots and feedback must total no more than 16 MiB.")
        except ValueError:
            raise HTTPException(400, "Invalid upload length.") from None

    async def bounded_stream():
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > MAX_BODY_BYTES:
                raise MultiPartException("Screenshots and feedback must total no more than 16 MiB.")
            yield chunk

    parser = _FeedbackMultipartParser(request.headers, bounded_stream(), max_files=MAX_FILES,
                                     max_fields=3, max_part_size=16000)
    form = None
    try:
        form = await parser.parse()
        fields = {}
        images = []
        for name, value in form.multi_items():
            if isinstance(value, UploadFile):
                if name != "files" or value.content_type not in _TYPES:
                    raise HTTPException(422, "Choose PNG, JPEG or static WebP screenshots.")
                image = await value.read(MAX_FILE_BYTES + 1)
                if not image or len(image) > MAX_FILE_BYTES:
                    raise HTTPException(422, "Each screenshot must contain an image no larger than 5 MiB.")
                images.append(image)
            else:
                if name not in {"type", "message", "page_url"} or name in fields:
                    raise HTTPException(422, "Invalid feedback form fields.")
                fields[name] = value
        if not images:
            raise HTTPException(422, "Choose at least one screenshot.")
        try:
            return FeedbackCreate.model_validate(fields), images
        except ValidationError:
            raise HTTPException(422, "Include a description of 5–4,000 characters and a valid feedback category.") from None
    except (MultiPartException, ValueError, LookupError) as exc:
        # Parser errors are our static messages or bounded Starlette limit messages; never echo headers.
        raise HTTPException(413, "Upload is too large or malformed. Use up to three screenshots, 5 MiB each.") from exc
    finally:
        if form is not None:
            with anyio.CancelScope(shield=True):
                await form.close()
        else:
            # Starlette closes on parser errors, but not on cancellation/client disconnect.
            for file in parser._files_to_close_on_error:
                file.close()


@router.post("/with-attachments", response_model=FeedbackResponse | FeedbackSubmissionStatus, status_code=201)
async def submit_feedback_with_attachments(request: Request, response: Response,
                                           current_user: User = Depends(get_current_user),
                                           db: Session = Depends(get_db)):
    # No File/UploadFile dependency: all of these checks precede the first receive/parse.
    user_id, email = current_user.id, current_user.email
    _check_reader(request, user_id, required=True)
    if (request.headers.get("origin") not in settings.CORS_ORIGINS
            or request.headers.get("x-requested-with") != "XMLHttpRequest"):
        raise HTTPException(403, "Open feedback on EarningsNerd before attaching screenshots.")
    submission_key = _key(request.headers.get("idempotency-key"))
    if submission_key is None:
        raise HTTPException(422, "A submission identifier is required.")
    if not settings.FEEDBACK_MEDIA_ENABLED or not settings.FEEDBACK_MEDIA_BUCKET:
        raise HTTPException(503, "Screenshots are temporarily unavailable. Your draft has been kept.")
    enforce_rate_limit(request, MEDIA_INGRESS_LIMITER, f"feedback-media:{user_id}", include_client_ip=False,
                       error_detail="Screenshot uploads are temporarily limited. Please retry later.")
    if not _UPLOAD_SLOTS.acquire(blocking=False):
        raise HTTPException(503, "Screenshot uploads are busy. Please retry shortly.", headers={"Retry-After": "5"})
    claim = None
    try:
        async with request_work_scope():
            await run_owned_sync(filing_list_service.release_request_session, db)
            # This inner deadline owns body receipt and native/provider work, whereas the outer
            # middleware deadline alone can abandon the ASGI task after returning its 504.
            async with asyncio.timeout(55):
                payload, images = await _read_upload(request)
                fingerprint = await run_owned_sync(submissions.payload_fingerprint, payload, images)
                claim = await run_owned_sync(_db_unit, db, submissions.claim_submission,
                                             user_id, submission_key, fingerprint)
                if claim.attempt_token is None:
                    return _claim_response(claim)
                normalized = [await normalize_feedback_image(image) for image in images]
                manifests = await run_owned_sync(_db_unit, db, submissions.reserve_attachments,
                                                 user_id, claim, normalized)
                generations = {}
                for manifest, image in zip(manifests, normalized, strict=True):
                    generations[manifest.id] = await run_feedback_storage_operation(
                        settings.FEEDBACK_MEDIA_BUCKET, "upload", manifest.object_key, data=image.data,
                    )
                saved = await run_owned_sync(_db_unit, db, submissions.publish_submission, user_id, claim,
                                             payload, _hash_ip(_client_ip(request)), generations,
                                             settings.FEEDBACK_MEDIA_RETENTION_DAYS)
        response.headers.update(_PRIVATE_HEADERS)
        await _after_saved(user_id, email, saved, payload, len(images))
        return saved
    except submissions.FeedbackSubmissionError as exc:
        raise _error(exc) from None
    except FeedbackImageError as exc:
        raise HTTPException(422, str(exc)) from None
    except (FeedbackImageBusy, FeedbackImageTimeout):
        raise HTTPException(503, "Screenshots could not be processed. Your draft is ready to retry.",
                            headers={"Retry-After": "5"}) from None
    except FeedbackStorageError:
        raise HTTPException(503, "Screenshots could not be saved. Your draft is ready to retry.") from None
    except TimeoutError:
        raise HTTPException(504, "Sending took too long. Check the receipt before retrying.") from None
    finally:
        try:
            if claim is not None and claim.attempt_token is not None:
                with anyio.CancelScope(shield=True):
                    async with request_work_scope():
                        await run_owned_sync(_db_unit, db, submissions.fail_attempt, user_id, claim)
        finally:
            _UPLOAD_SLOTS.release()


@router.get("/submissions/{submission_id}", response_model=FeedbackSubmissionStatus)
async def feedback_submission_status(submission_id: str, request: Request, response: Response,
                                     current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user_id = current_user.id
    _check_reader(request, user_id)
    key = _key(submission_id)
    try:
        async with request_work_scope():
            result = await run_owned_sync(_db_unit, db, submissions.read_receipt, user_id, key)
    except submissions.FeedbackSubmissionError as exc:
        raise _error(exc) from None
    response.headers.update(_PRIVATE_HEADERS)
    return result


@router.get("/attachments/{attachment_id}")
async def feedback_attachment(attachment_id: str, request: Request, current_user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    user_id = current_user.id
    _check_reader(request, user_id)
    try:
        async with request_work_scope():
            media = await run_owned_sync(_db_unit, db, submissions.read_private_media,
                                         attachment_id, user_id)
            data = await run_feedback_storage_operation(settings.FEEDBACK_MEDIA_BUCKET, "download", media.object_key,
                                                        generation=media.object_generation)
            # Deletion/expiry may have occurred during storage I/O. Recheck before releasing bytes.
            await run_owned_sync(_db_unit, db, submissions.read_private_media, attachment_id, user_id)
        if len(data) != media.byte_count or hashlib.sha256(data).hexdigest() != media.checksum:
            raise HTTPException(503, "This screenshot could not be loaded. Please retry.")
        return Response(data, media_type="image/png", headers={
            **_PRIVATE_HEADERS, "Content-Disposition": 'inline; filename="feedback-screenshot.png"',
        })
    except submissions.FeedbackSubmissionError as exc:
        raise _error(exc) from None
    except FeedbackStorageError:
        raise HTTPException(503, "This screenshot could not be loaded. Please retry.") from None


async def _notify_admin(user_id: int, user_email: str | None, feedback_id: int, payload: FeedbackCreate,
                        attachment_count: int = 0) -> None:
    admin_email = settings.FEEDBACK_NOTIFICATION_EMAIL
    if not admin_email:
        return
    safe_email = html.escape(user_email or "")
    safe_message = html.escape(payload.message)
    inbox_url = html.escape(settings.FRONTEND_URL.rstrip("/") + "/admin/feedback", quote=True)
    page_html = (
        f'<p><strong>Page:</strong> {html.escape(payload.page_url)}</p>' if payload.page_url else ""
    )
    body = f"""
    <div style="font-family:Arial,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:16px;">
      <h2 style="margin:0 0 12px;">New beta feedback — {html.escape(payload.type)}</h2>
      <p><strong>From:</strong> {safe_email} (user #{user_id})</p>
      {page_html}
      <p><strong>Screenshots:</strong> {attachment_count} — <a href="{inbox_url}">Open feedback inbox</a>.</p>
      <div style="background:#f9f9f9;border-left:4px solid #10B981;padding:12px;margin-top:8px;white-space:pre-wrap;">{safe_message}</div>
      <p style="color:#666;font-size:12px;margin-top:12px;">Feedback #{feedback_id}</p>
    </div>
    """
    await send_email(
        to=[admin_email],
        # Plain-text subject: use the raw email, not the HTML-escaped one (no &amp; entities here).
        subject=f"[Beta feedback] {payload.type} from {user_email or ''}",
        html=body,
        reply_to=user_email,
    )
