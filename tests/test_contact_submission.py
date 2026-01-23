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
        
    except Exception as e:
        # Rollback in case the error was a DB error during add/commit
        # If it was an AssertionError, this rollback might be redundant but harmless
        db_session.rollback()
        # Fail the test explicitly with a message if it wasn't an assertion error
        if not isinstance(e, AssertionError):
            pytest.fail(f"Failed to insert contact with 64-char IP: {str(e)}")
        else:
            raise e
    finally:
        # Clean up regardless of success or failure
        # We check if contact was persisted (has an ID) and exists in the session
        if contact.id:
            try:
                # Merge checks if object is in session, if not adds it. 
                # Since we are in the same session, we can just delete.
                # But if rollback happened, contact might be transient or detached if session was closed (it's not).
                # If rollback happened, contact.id might still be set on the python object but not in DB?
                # Actually if db_session.commit() succeeded, contact is in DB.
                # If exception was AssertionError, commit succeeded.
                # If exception was during commit, rollback happened, so not in DB.
                
                # Check if it exists in DB to be safe, or just try delete
                # But if we just rolled back, delete might fail or warn.
                
                # Re-query or merge to ensure attached?
                # Simplest is:
                db_session.delete(contact)
                db_session.commit()
            except Exception:
                # If delete fails (e.g. because it was already rolled back), just ignore in finally
                db_session.rollback()
