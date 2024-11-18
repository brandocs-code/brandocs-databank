import os
from flask import Flask, render_template, jsonify, request, redirect, url_for, make_response
from email_utils import EmailMonitor
from models.models import db, Email, Company, CompanyEmail
from datetime import datetime
import json
from sqlalchemy.sql import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
import time
import logging
import pytz
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import create_engine
from functools import wraps
import sys
from flask_migrate import Migrate

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Handle timezone based on Python version
try:
    from backports.zoneinfo import ZoneInfo
except ImportError:
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        import pytz
        def ZoneInfo(tz_name):
            return pytz.timezone(tz_name)
    logger.info("Using backports.zoneinfo for Python < 3.9")

# Initialize timezone
budapest_tz = ZoneInfo('Europe/Budapest')

app = Flask(__name__)

# Configure Flask app
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "dev_key_only"
app.config['JSON_SORT_KEYS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Configure database based on environment
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    raise ValueError("DATABASE_URL environment variable is required")

# Configure SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 280,
    'pool_size': int(os.environ.get('SQLALCHEMY_POOL_SIZE', '5')),
    'max_overflow': int(os.environ.get('SQLALCHEMY_MAX_OVERFLOW', '10')),
    'pool_timeout': int(os.environ.get('SQLALCHEMY_POOL_TIMEOUT', '30')),
}

# Initialize Flask-SQLAlchemy
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Create engine and session factory with improved error handling
def create_db_engine():
    max_retries = 3
    retry_delay = 1
    last_error = None

    for attempt in range(max_retries):
        try:
            engine = create_engine(
                database_url,
                **app.config['SQLALCHEMY_ENGINE_OPTIONS']
            )
            # Test connection
            with engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            return engine
        except Exception as e:
            last_error = str(e)
            logger.error(f"Failed to create engine (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise OperationalError("Failed to create database engine", last_error)

engine = create_db_engine()
Session = scoped_session(sessionmaker(bind=engine))

# Initialize email monitor with improved error handling
def initialize_email_monitor():
    required_env_vars = ['EMAIL_USERNAME', 'EMAIL_PASSWORD', 'EMAIL_SERVER']
    missing_vars = [var for var in required_env_vars if not os.environ.get(var)]
    
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    try:
        monitor = EmailMonitor(
            username=os.environ.get('EMAIL_USERNAME'),
            password=os.environ.get('EMAIL_PASSWORD'),
            server=os.environ.get('EMAIL_SERVER')
        )
        # Test connection
        success, message = monitor.test_connection()
        if not success:
            raise Exception(f"Email connection test failed: {message}")
        return monitor
    except Exception as e:
        logger.error(f"Failed to initialize email monitor: {str(e)}")
        raise

email_monitor = initialize_email_monitor()

def get_db():
    """Get database session with improved connection handling"""
    max_retries = 3
    retry_delay = 1
    last_error = None
    session = None
    
    for attempt in range(max_retries):
        try:
            session = Session()
            # Test connection
            session.execute(text('SELECT 1'))
            return session
        except Exception as e:
            last_error = str(e)
            logger.error(f"Database connection error (attempt {attempt + 1}): {str(e)}")
            if session:
                try:
                    session.close()
                except:
                    pass
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                try:
                    Session.remove()
                except:
                    pass
                continue
            raise OperationalError("Failed to connect to database after multiple attempts", last_error)

@app.before_request
def before_request():
    """Ensure database connection before each request"""
    try:
        session = get_db()
        if session:
            session.close()
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        if request.path.startswith('/api/'):
            response = jsonify({
                'success': False,
                'error': 'Database connection error',
                'message': 'Unable to connect to database. Please try again later.'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 503
        return "Database connection error. Please try again later.", 503

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Properly cleanup database session"""
    try:
        Session.remove()
    except Exception as e:
        logger.error(f"Error during session cleanup: {str(e)}")

# Security middleware
def check_auth(username, password):
    """Check if a username/password combination is valid."""
    return (username == os.environ.get('BASIC_AUTH_USERNAME') and
            password == os.environ.get('BASIC_AUTH_PASSWORD'))

def authenticate():
    """Send a 401 response that enables basic auth."""
    return ('Could not verify your access level for that URL.\n'
            'You have to login with proper credentials', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if os.environ.get('BASIC_AUTH_USERNAME'):
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password):
                return authenticate()
        return f(*args, **kwargs)
    return decorated

@app.route('/')
@requires_auth
def index():
    return render_template('index.html')

@app.route('/companies')
@requires_auth
def companies():
    return render_template('companies.html')

@app.route('/api/companies', methods=['GET'])
@requires_auth
def get_companies():
    try:
        session = get_db()
        companies = session.query(Company).all()
        
        company_list = []
        for company in companies:
            company_data = {
                'id': company.id,
                'name': company.name,
                'emails': [e.email for e in company.emails],
                'email_count': len(company.emails)
            }
            company_list.append(company_data)
        
        response = jsonify({
            'success': True,
            'data': company_list
        })
        response.headers['Content-Type'] = 'application/json'
        return response
    except Exception as e:
        logger.error(f"Error in get_companies: {str(e)}")
        response = jsonify({
            'success': False,
            'error': str(e)
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@app.route('/api/companies', methods=['POST'])
@requires_auth
def create_company():
    try:
        # Ensure proper content type
        if not request.is_json:
            response = jsonify({
                'success': False,
                'error': 'Content type must be application/json'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 415
            
        session = get_db()
        data = request.get_json()
        
        if not data or not data.get('name'):
            response = jsonify({
                'success': False,
                'error': 'Missing company name',
                'message': 'A cégnév megadása kötelező'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 400
            
        company = Company(name=data['name'])
        session.add(company)
        
        if data.get('emails'):
            for email in data['emails']:
                company_email = CompanyEmail(company=company, email=email)
                session.add(company_email)
        
        session.commit()
        
        response = jsonify({
            'success': True,
            'data': {
                'id': company.id,
                'name': company.name,
                'emails': [e.email for e in company.emails]
            }
        })
        response.headers['Content-Type'] = 'application/json'
        return response
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in create_company: {str(e)}")
        if session:
            session.rollback()
        response = jsonify({
            'success': False,
            'error': 'Database error occurred',
            'message': 'Nem sikerült létrehozni a céget'
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@app.route('/api/stats')
@requires_auth
def get_stats():
    try:
        session = get_db()
        companies_count = session.query(Company).count()
        pdf_count = session.query(Email).filter_by(has_pdf=True).count()
        email_count = session.query(Email).count()
        
        response = jsonify({
            'success': True,
            'stats': {
                'companies': companies_count,
                'pdfs': pdf_count,
                'emails': email_count
            }
        })
        response.headers['Content-Type'] = 'application/json'
        return response
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in stats: {str(e)}")
        response = jsonify({
            'success': False,
            'error': 'Database error occurred',
            'message': 'Unable to fetch statistics. Please try again later.'
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500
    except Exception as e:
        logger.error(f"Unexpected error in stats: {str(e)}")
        response = jsonify({
            'success': False,
            'error': 'An unexpected error occurred',
            'message': 'Unable to process your request. Please try again later.'
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@app.route('/api/emails')
@requires_auth
def get_emails():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10
        session = get_db()
        
        # Calculate offset
        offset = (page - 1) * per_page
        
        # Get total count
        total = session.query(Email).count()
        
        # Get emails for current page
        emails = session.query(Email).order_by(Email.date.desc()).offset(offset).limit(per_page).all()
        
        # Prepare response data
        email_list = []
        for email in emails:
            # Convert to Budapest timezone for display
            display_date = pytz.UTC.localize(email.date).astimezone(budapest_tz)
            
            email_data = {
                'id': email.id,
                'subject': email.subject,
                'from': email.sender,
                'date': display_date.isoformat(),
                'has_pdf': email.has_pdf,
                'pdf_emails': email.pdf_emails.split(',') if email.pdf_emails else []
            }
            
            # Add company info if available
            if email.company:
                email_data['company'] = {
                    'name': email.company.name,
                    'emails': [e.email for e in email.company.emails]
                }
            
            email_list.append(email_data)
        
        response = jsonify({
            'success': True,
            'data': email_list,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        })
        response.headers['Content-Type'] = 'application/json'
        return response
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_emails: {str(e)}")
        response = jsonify({
            'success': False,
            'error': 'Database error occurred',
            'message': 'Unable to fetch emails. Please try again later.'
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500
    except Exception as e:
        logger.error(f"Unexpected error in get_emails: {str(e)}")
        response = jsonify({
            'success': False,
            'error': 'An unexpected error occurred',
            'message': 'Unable to process your request. Please try again later.'
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@app.route('/check-latest')
@requires_auth
def check_latest():
    """Check latest email with improved error handling and logging"""
    logger.info("Checking for latest email...")
    try:
        # Initialize/test email connection first
        success, message = email_monitor.test_connection()
        if not success:
            logger.error(f"Email connection test failed: {message}")
            response = jsonify({
                'success': False,
                'error': 'Email connection error',
                'message': 'Failed to connect to email server. Please try again later.'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 503

        success, data = email_monitor.check_latest_email()
        logger.info(f"Check result: success={success}, data={data}")
        
        if not success:
            error_msg = data.get('error', 'Unknown error occurred')
            logger.error(f"Failed to check latest email: {error_msg}")
            response = jsonify({
                'success': False,
                'error': error_msg,
                'message': 'Failed to check latest email. Please try again later.'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 500
            
        if isinstance(data, dict) and not data.get('error'):
            try:
                session = get_db()
                existing_email = session.query(Email).filter_by(
                    sender=data['from'],
                    subject=data.get('subject', '')
                ).first()
                
                if existing_email:
                    logger.info("Email already exists in database")
                    response = jsonify({'success': True, 'data': None})
                    response.headers['Content-Type'] = 'application/json'
                    return response
                
                # Create new Email record with improved error handling
                try:
                    email_record = Email()
                    email_record.sender = data['from']
                    email_record.subject = data.get('subject', '')
                    
                    # Parse date with timezone handling
                    if data.get('date'):
                        try:
                            email_date = datetime.strptime(str(data['date']), '%a, %d %b %Y %H:%M:%S %z')
                            email_record.date = email_date.astimezone(pytz.UTC)
                        except (ValueError, TypeError) as e:
                            logger.error(f"Date parsing error: {str(e)}")
                            email_record.date = datetime.now(pytz.UTC)
                    else:
                        email_record.date = datetime.now(pytz.UTC)
                    
                    email_record.has_pdf = data.get('has_pdf', False)
                    if data.get('pdf_emails'):
                        email_record.pdf_emails = ','.join(data['pdf_emails'])
                    
                    # Try to find matching company
                    if data.get('from'):
                        company = session.query(Company).join(CompanyEmail).filter(
                            CompanyEmail.email == data['from']
                        ).first()
                        if company:
                            email_record.company = company
                    
                    session.add(email_record)
                    session.commit()
                    logger.info("Successfully saved new email record")
                    
                    response = jsonify({'success': True, 'data': data})
                    response.headers['Content-Type'] = 'application/json'
                    return response
                    
                except Exception as e:
                    session.rollback()
                    logger.error(f"Error saving email record: {str(e)}")
                    raise
                    
            except Exception as e:
                logger.error(f"Database error processing email: {str(e)}")
                response = jsonify({
                    'success': False,
                    'error': str(e),
                    'message': 'Failed to process email data. Please try again later.'
                })
                response.headers['Content-Type'] = 'application/json'
                return response, 500
                
        response = jsonify({'success': True, 'data': data})
        response.headers['Content-Type'] = 'application/json'
        return response
        
    except Exception as e:
        logger.error(f"Unexpected error in check_latest: {str(e)}")
        response = jsonify({
            'success': False,
            'error': str(e),
            'message': 'An unexpected error occurred. Please try again later.'
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

@app.route('/api/companies/<int:id>', methods=['DELETE'])
@requires_auth
def delete_company(id):
    try:
        session = get_db()
        company = session.query(Company).get(id)
        if not company:
            return jsonify({'success': False, 'message': 'Cég nem található'}), 404
            
        session.delete(company)
        session.commit()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting company: {str(e)}")
        return jsonify({'success': False, 'message': 'Nem sikerült törölni a céget'}), 500

@app.route('/api/companies/<int:id>', methods=['PUT'])
@requires_auth
def update_company(id):
    try:
        session = get_db()
        company = session.query(Company).get(id)
        if not company:
            return jsonify({'success': False, 'message': 'Cég nem található'}), 404
            
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Invalid JSON data'}), 400
            
        company.name = data.get('name', company.name)
        
        # Update emails
        if 'emails' in data:
            # Remove old emails
            session.query(CompanyEmail).filter_by(company_id=company.id).delete()
            
            # Add new emails
            for email in data['emails']:
                company_email = CompanyEmail(company=company, email=email)
                session.add(company_email)
                
        session.commit()
        return jsonify({
            'success': True,
            'data': {
                'id': company.id,
                'name': company.name,
                'emails': [e.email for e in company.emails]
            }
        })
    except Exception as e:
        logger.error(f"Error updating company: {str(e)}")
        return jsonify({'success': False, 'message': 'Nem sikerült módosítani a céget'}), 500

@app.route('/api/companies/<int:id>', methods=['GET'])
@requires_auth
def get_company(id):
    try:
        session = get_db()
        company = session.query(Company).get(id)
        
        if not company:
            response = jsonify({
                'success': False,
                'error': 'Company not found',
                'message': 'A megadott cég nem található'
            })
            response.headers['Content-Type'] = 'application/json'
            return response, 404
            
        company_data = {
            'id': company.id,
            'name': company.name,
            'emails': [e.email for e in company.emails]
        }
        
        response = jsonify({
            'success': True,
            'data': company_data
        })
        response.headers['Content-Type'] = 'application/json'
        return response
        
    except SQLAlchemyError as e:
        logger.error(f"Database error in get_company: {str(e)}")
        if session:
            session.rollback()
        response = jsonify({
            'success': False,
            'error': 'Database error occurred',
            'message': 'Nem sikerült lekérni a cég adatait'
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500
    except Exception as e:
        logger.error(f"Unexpected error in get_company: {str(e)}")
        response = jsonify({
            'success': False,
            'error': 'An unexpected error occurred',
            'message': 'Nem sikerült feldolgozni a kérést'
        })
        response.headers['Content-Type'] = 'application/json'
        return response, 500

# Gunicorn configuration
if 'gunicorn' in sys.argv:
    from gunicorn.app.base import BaseApplication
    from gunicorn.workers.gevent import GeventWorker

    class FlaskApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            config = {
                key: value for key, value in self.options.items() if key in self.cfg.settings
            }
            for key, value in config.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    # Initialize Gunicorn with options
    options = {
        'bind': '0.0.0.0:5000',
        'workers': int(os.environ.get('GUNICORN_WORKERS', '2')),
        'worker_class': 'gunicorn.workers.gevent.GeventWorker',
        'timeout': int(os.environ.get('GUNICORN_TIMEOUT', '30')),
        'accesslog': '-',
        'errorlog': '-'
    }

    # Start Gunicorn
    FlaskApplication(app, options).run()

# Main Flask app execution
if __name__ == '__main__':
    # Get port from environment variable with fallback to 5000
    port = int(os.environ.get('PORT', 5000))
    # Bind to all interfaces (0.0.0.0) to make it accessible externally
    app.run(host='0.0.0.0', port=port)