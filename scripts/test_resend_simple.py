import asyncio
import os
import sys
from dotenv import load_dotenv

# Load .env from backend directory
sys.path.append(os.path.join(os.getcwd(), "backend"))
load_dotenv("backend/.env")

from app.config import settings
from app.services.resend_service import send_email, ResendError

async def test_resend():
    print(f"Testing Resend Configuration...")
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
        print(f"\n❌ Failed to send email.")
        print(f"Error: {e}")
    except Exception as e:
        print(f"\n❌ An unexpected error occurred.")
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_resend())
