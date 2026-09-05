"""Manual live Resend configuration smoke (NOT a pytest test).

Run only when explicitly intending to email neil@earningsnerd.io:
    python /path/to/repo/backend/scripts/smoke_resend.py

Loads backend/.env independent of the working directory. Importing does not send.
"""

import asyncio
from pathlib import Path
import sys
from dotenv import load_dotenv

# Load .env from backend directory
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from app.config import settings  # noqa: E402 — bootstrap script path and dotenv first
from app.services.resend_service import send_email, ResendError  # noqa: E402

async def smoke_resend() -> None:
    print("Testing Resend Configuration...")
    print(f"RESEND_FROM_EMAIL: {settings.RESEND_FROM_EMAIL}")
    print(f"RESEND_API_KEY: {'*' * 5 + settings.RESEND_API_KEY[-4:] if settings.RESEND_API_KEY else 'NOT SET'}")
    
    # Use the email from the DNS file as a likely target for testing
    test_email = "neil@earningsnerd.io"
    print(f"Attempting to send test email to: {test_email}")

    try:
        result = await send_email(
            to=[test_email],
            subject="Resend Configuration Test",
            html="<p>If you received this, Resend is working correctly!</p>"
        )
        print("\n✅ Success! Email sent.")
        print(f"ID: {result.get('id')}")
    except ResendError as e:
        print("\n❌ Failed to send email.")
        print(f"Error: {e}")
    except Exception as e:
        print("\n❌ An unexpected error occurred.")
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(smoke_resend())
