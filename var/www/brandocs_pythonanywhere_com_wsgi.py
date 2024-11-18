import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import pymysql
from datetime import datetime
import time
from sqlalchemy import text

# Configure logging
handler = RotatingFileHandler('/home/Brandocs/brandocs_pythonanywhere_com.log', maxBytes=10000000, backupCount=5)
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# Configure database URL
os.environ['DATABASE_URL'] = 'mysql://Brandocs:' + os.environ.get('MYSQL_PASSWORD', '') + '@Brandocs.mysql.pythonanywhere-services.com/Brandocs$default'

# Set database configuration
os.environ['SQLALCHEMY_POOL_SIZE'] = '5'
os.environ['SQLALCHEMY_MAX_OVERFLOW'] = '10'
os.environ['SQLALCHEMY_POOL_TIMEOUT'] = '30'
os.environ['SQLALCHEMY_POOL_RECYCLE'] = '280'

# Add project directory to Python path
path = '/home/Brandocs/brandocs'
if path not in sys.path:
    sys.path.append(path)
    logger.info(f"Added {path} to Python path")

try:
    # Install PyMySQL as MySQLdb
    pymysql.install_as_MySQLdb()
    logger.info("Successfully installed PyMySQL as MySQLdb")
    
    # Import Flask application
    from app import app as application
    logger.info("Successfully imported Flask application")

    # Initialize database with improved retry mechanism
    max_retries = 3
    retry_delay = 1

    for attempt in range(max_retries):
        try:
            with application.app_context():
                from models.models import db
                db.create_all()
                
                # Test database connection
                engine = db.get_engine()
                with engine.connect() as conn:
                    conn.execute(text('SELECT 1'))
                
                logger.info("Database initialized successfully")
                break
        except Exception as e:
            logger.error(f"Database initialization attempt {attempt + 1} failed: {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(retry_delay * (attempt + 1))

except Exception as e:
    logger.error(f"Failed to initialize application: {str(e)}")
    raise

# Log successful startup
logger.info(f"Application successfully initialized at {datetime.now().isoformat()}")
