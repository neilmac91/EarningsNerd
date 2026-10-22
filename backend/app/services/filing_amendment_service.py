"""Keep amendments and their originals linked without replacing accession-specific content."""
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models import Company, Filing


def expand_amendment_forms(forms: list[str]) -> list[str]:
    """Expand domestic financial reports only; explicit amended-only queries stay exact."""
    result = list(dict.fromkeys(forms))
    for form in forms:
        if form in ("10-K", "10-Q") and f"{form}/A" not in result:
            result.append(f"{form}/A")
    return result


def lock_company_filings(db: Session, company_id: int) -> None:
    """Take the company row's lock that serializes its filing writers, held until the transaction ends.

    Each writer of a company's filing rows takes it before it reads or writes any of them, so a
    competing writer of that company has committed, and is seen, before it inserts. Read first, two
    writers both find a filing missing and the second insert fails the unique accession, rolling back
    its batch (E123's review); taken first, it also keeps every writer to one lock order, the company
    and then its filing rows. The row lock reaches every process and instance, as a process lock would
    not. It serializes one company's writers only: a filing listed under two companies (a co-registrant
    filing) is checked under two locks. PostgreSQL emits FOR NO KEY UPDATE, which does not conflict
    with the key-share locks child-row inserts take; SQLite omits the clause. Taking it again in the
    same transaction is a no-op.
    """
    with db.no_autoflush:
        db.query(Company.id).filter(Company.id == company_id).with_for_update(key_share=True).scalar()


def mark_superseded_filings(db: Session, company_id: int) -> int:
    """Mark older same-period rows in the caller's transaction, in either ingestion order.

    No period means no defensible relationship. Select metadata only in one company query;
    update the changed rows in one executemany batch, without loading XBRL or summaries.
    """
    # Serialize competing refreshes. Lock before reading links, and before flushing new rows.
    lock_company_filings(db, company_id)
    db.flush()
    rows = db.query(
        Filing.id, Filing.filing_type, Filing.period_end_date, Filing.filing_date,
        Filing.accession_number, Filing.superseded_by_accession,
    ).filter(
        Filing.company_id == company_id,
        Filing.filing_type.in_(("10-K", "10-K/A", "10-Q", "10-Q/A")),
        Filing.period_end_date.isnot(None),
    ).all()
    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        groups[(row.filing_type.removesuffix("/A"), row.period_end_date)].append(row)
    updates = []
    for group in groups.values():
        amendments = [row for row in group if row.filing_type.endswith("/A")]
        if not amendments:
            continue
        newest = max(amendments, key=lambda row: (row.filing_date, row.accession_number))
        for row in group:
            if row.id != newest.id and (row.filing_date, row.accession_number) < (
                newest.filing_date, newest.accession_number
            ) and row.superseded_by_accession != newest.accession_number:
                updates.append({"id": row.id, "superseded_by_accession": newest.accession_number})
    if updates:
        db.bulk_update_mappings(Filing, updates)
        # Bulk mappings bypass the identity map; avoid serializing stale relationships from
        # already-loaded Filing objects before the caller's commit (expire_on_commit may be off).
        for obj in list(db.identity_map.values()):
            if isinstance(obj, Filing) and obj.company_id == company_id:
                db.expire(obj, ["superseded_by_accession"])
    return len(updates)
