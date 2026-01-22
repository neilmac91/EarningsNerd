import sys
import os
import logging
from sqlalchemy import text

# Add backend directory to path so we can import app
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

try:
    from app.database import engine
except ImportError:
    # Try alternative path if running from root
    sys.path.append(os.path.join(os.getcwd(), 'backend'))
    from app.database import engine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_contact_column():
    """
    Checks the database dialect and alters the contact_submissions.ip_address 
    column to VARCHAR(64) if using PostgreSQL.
    """
    try:
        logger.info(f"Connecting to database with dialect: {engine.dialect.name}")
        
        with engine.connect() as connection:
            if engine.dialect.name == 'postgresql':
                logger.info("Detected PostgreSQL database. Attempting to alter column...")
                # Use text() for raw SQL
                sql = text("ALTER TABLE contact_submissions ALTER COLUMN ip_address TYPE VARCHAR(64);")
                connection.execute(sql)
                connection.commit()
                logger.info("Successfully altered ip_address column to VARCHAR(64).")
                
            elif engine.dialect.name == 'sqlite':
                logger.info("Detected SQLite database.")
                logger.info("SQLite does not enforce VARCHAR length limits. Skipping ALTER COLUMN.")
                # We could recreate the table here if strict enforcement was needed,
                # but for this specific request, logging is sufficient as per requirements.
                
            else:
                logger.warning(f"Unsupported database dialect: {engine.dialect.name}. No changes made.")

    except Exception as e:
        logger.error(f"An error occurred while fixing the contact column: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    fix_contact_column()
