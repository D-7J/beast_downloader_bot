"""
Database initialization script for Beast Downloader Bot.
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info("Loaded environment variables from .env file")
    else:
        logger.warning("No .env file found, using system environment variables")

    # Validate required environment variables
    required_vars = [
        'DATABASE_URL',
        'BOT_TOKEN',
        'ADMIN_IDS'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

def create_database_tables(engine):
    """Create database tables if they don't exist."""
    from database.models import Base
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Create initial admin user if not exists
        with engine.connect() as conn:
            # Check if users table has any admin users
            result = conn.execute(
                text("SELECT id FROM users WHERE is_admin = TRUE LIMIT 1")
            ).fetchone()
            
            if not result:
                # Create initial admin user
                admin_ids = [int(id_str.strip()) for id_str in os.getenv('ADMIN_IDS').split(',')]
                for admin_id in admin_ids:
                    conn.execute(
                        text("""
                        INSERT INTO users (id, username, is_admin, is_active, created_at, updated_at)
                        VALUES (:id, 'admin', TRUE, TRUE, NOW(), NOW())
                        ON CONFLICT (id) DO UPDATE 
                        SET is_admin = TRUE, is_active = TRUE, updated_at = NOW()
                        """),
                        {'id': admin_id}
                    )
                conn.commit()
                logger.info(f"Created/updated admin users with IDs: {admin_ids}")
        
    except SQLAlchemyError as e:
        logger.error(f"Error creating database tables: {e}")
        sys.exit(1)

def main():
    """Main function to initialize the database."""
    # Load environment variables
    load_environment()
    
    # Get database URL
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        sys.exit(1)
    
    # Create database engine
    try:
        engine = create_engine(database_url)
        
        # Test database connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        logger.info("Successfully connected to the database")
        
        # Create tables and initial data
        create_database_tables(engine)
        
        logger.info("Database initialization completed successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Database connection error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Add parent directory to path to allow importing database models
    sys.path.append(str(Path(__file__).parent.parent))
    
    # Import models after adding to path
    from database import models  # noqa: F401
    
    main()
