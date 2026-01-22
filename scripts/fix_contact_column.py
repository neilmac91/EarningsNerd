import sys
import logging
from pathlib import Path
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add backend directory to path so we can import app
# Resolves to: <project_root>/backend
try:
    current_file = Path(__file__).resolve()
    # If run as script, current_file is the script path
    # Go up one level to 'scripts' (or whatever dir), then up to root, then 'backend'
    # Actually, if script is in <root>/scripts/fix_contact_column.py
    # parent = <root>/scripts
    # parent.parent = <root>
    # <root>/backend is what we want
    backend_dir = current_file.parent.parent / 'backend'
    
    if not backend_dir.exists():
        # Fallback for if directory structure is different or running from elsewhere
        # e.g. if running from root with python scripts/fix_contact_column.py, __file__ is relative
        # but resolve() handles that.
        # Let's try current working directory as fallback for safety
        backend_dir = Path.cwd() / 'backend'

    sys.path.append(str(backend_dir))
    logger.info(f"Added {backend_dir} to sys.path")

    from app.database import engine
except ImportError as e:
    logger.error(f"Could not import app.database. Ensure you are running from the project root or the backend directory is accessible. Error: {e}")
    sys.exit(1)

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
