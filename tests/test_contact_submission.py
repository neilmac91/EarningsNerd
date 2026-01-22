import pytest
from app.database import SessionLocal, engine, Base
from app.models.contact import ContactSubmission
from sqlalchemy.orm import Session

@pytest.fixture(scope="module")
def db_session():
    # Ensure tables exist (important for SQLite in-memory or fresh dbs)
    Base.metadata.create_all(bind=engine)
    
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()

def test_contact_submission_long_ip(db_session: Session):
    """
    Verifies that a ContactSubmission can be saved with a 64-character IP address.
    This confirms the database column is wide enough.
    """
    # Create a 64-character string
    long_ip = "2001:0db8:85a3:0000:0000:8a2e:0370:7334" + "x" * 25 # 39 + 25 = 64 chars total
    # Adjust to exactly 64 chars just to be precise with the requirement
    long_ip = "x" * 64
    
    contact = ContactSubmission(
        name="Integration Test User",
        email="test_long_ip@example.com",
        subject="Testing Long IP",
        message="This is a test message to verify IP column length.",
        ip_address=long_ip
    )
    
    try:
        db_session.add(contact)
        db_session.commit()
        db_session.refresh(contact)
        
        assert contact.id is not None
        assert contact.ip_address == long_ip
        assert len(contact.ip_address) == 64
        
        # Clean up
        db_session.delete(contact)
        db_session.commit()
        
    except Exception as e:
        db_session.rollback()
        pytest.fail(f"Failed to insert contact with 64-char IP: {str(e)}")
