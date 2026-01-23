import sys
import logging
from pathlib import Path
from sqlalchemy import text, inspect

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add backend directory to path so we can import app
try:
    current_file = Path(__file__).resolve()
    # Go up one level to 'scripts', then up to root, then 'backend'
    backend_dir = current_file.parent.parent / 'backend'
    
    if not backend_dir.exists():
        # Fallback
        backend_dir = Path.cwd() / 'backend'

    sys.path.append(str(backend_dir))
    logger.info(f"Added {backend_dir} to sys.path")

    from app.database import engine
except ImportError as e:
    logger.error(f"Could not import app.database. Ensure you are running from the project root or the backend directory is accessible. Error: {e}")
    sys.exit(1)

def update_schema():
    """
    Checks if contact_submissions table exists and adds missing columns if needed.
    """
    try:
        logger.info(f"Connecting to database with dialect: {engine.dialect.name}")
        inspector = inspect(engine)
        table_name = "contact_submissions"
        
        if not inspector.has_table(table_name):
            logger.warning(f"Table '{table_name}' does not exist. Please run migration or startup script to create tables first.")
            return

        columns = [col['name'] for col in inspector.get_columns(table_name)]
        logger.info(f"Existing columns in '{table_name}': {columns}")

        with engine.connect() as connection:
            # Check and add ip_address
            if 'ip_address' not in columns:
                logger.info("Column 'ip_address' missing. Adding it...")
                if engine.dialect.name in ['sqlite', 'postgresql']:
                    # SQLite and Postgres support ADD COLUMN
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN ip_address VARCHAR(64)"))
                    connection.commit()
                    logger.info("Successfully added 'ip_address' column.")
                else:
                    logger.warning(f"Dialect {engine.dialect.name} not explicitly handled for ADD COLUMN, but trying standard SQL...")
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN ip_address VARCHAR(64)"))
                    connection.commit()
            else:
                logger.info("Column 'ip_address' already exists.")

            # Check and add subject
            if 'subject' not in columns:
                logger.info("Column 'subject' missing. Adding it...")
                if engine.dialect.name in ['sqlite', 'postgresql']:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN subject VARCHAR(200)"))
                    connection.commit()
                    logger.info("Successfully added 'subject' column.")
                else:
                    logger.warning(f"Dialect {engine.dialect.name} not explicitly handled for ADD COLUMN, but trying standard SQL...")
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN subject VARCHAR(200)"))
                    connection.commit()
            else:
                logger.info("Column 'subject' already exists.")

    except Exception as e:
        logger.error(f"An error occurred while updating the schema: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    update_schema()
