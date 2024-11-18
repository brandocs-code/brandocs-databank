import imaplib
import email
import re
import PyPDF2
import io
import ssl
from email.header import decode_header
from datetime import datetime
import logging
from email.utils import parsedate_to_datetime
import pytz
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class EmailMonitor:
    def __init__(self, username, password, server):
        """Initialize EmailMonitor with improved validation"""
        if not all([username, password, server]):
            raise ValueError("Email credentials are missing")
        self.username = username
        self.password = password
        self.server = server
        self.imap = None
        self.last_connection_time = None
        self.connection_timeout = 300  # 5 minutes timeout
        logger.info(f"EmailMonitor initialized with server: {server}")

    def _check_connection_state(self):
        """Check if the connection is active and in a valid state"""
        if not self.imap:
            return False
        try:
            status, _ = self.imap.noop()
            return status == 'OK'
        except:
            return False

    def _ensure_selected_state(self):
        """Ensure mailbox is selected and connection is valid"""
        if not self._check_connection_state():
            success, _ = self._connect()
            if not success:
                return False
        try:
            status, _ = self.imap.select('INBOX')
            return status == 'OK'
        except:
            return False

    def _connect(self):
        """Establish IMAP connection with improved error handling and connection pooling"""
        try:
            if self.imap:
                try:
                    self.imap.close()
                    self.imap.logout()
                except:
                    pass

            logger.info(f"Connecting to IMAP server: {self.server}")
            self.imap = imaplib.IMAP4_SSL(self.server, timeout=30)
            
            logger.info("Attempting login...")
            status, response = self.imap.login(self.username, self.password)
            if status != 'OK':
                raise imaplib.IMAP4.error(f"Login failed: {response[0].decode()}")
            
            self.last_connection_time = datetime.now()
            logger.info("Successfully connected to IMAP server")
            return True, None

        except Exception as e:
            self._disconnect()
            return False, str(e)

    def _disconnect(self):
        """Safely disconnect from IMAP server with improved cleanup"""
        if not self.imap:
            return

        try:
            try:
                self.imap.close()
                logger.info("IMAP connection closed")
            except Exception as e:
                logger.warning(f"Error during IMAP close: {str(e)}")

            try:
                self.imap.logout()
                logger.info("IMAP logout successful")
            except Exception as e:
                logger.warning(f"Error during IMAP logout: {str(e)}")
        finally:
            self.imap = None
            self.last_connection_time = None

    def _decode_email_header(self, header_value):
        """Decode email header with improved encoding handling"""
        if not header_value:
            return ""
        try:
            decoded_parts = decode_header(header_value)
            decoded_value = ""
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    try:
                        decoded_value += part.decode(encoding or 'utf-8', errors='replace')
                    except:
                        # Fallback to utf-8 if specified encoding fails
                        decoded_value += part.decode('utf-8', errors='replace')
                else:
                    decoded_value += str(part)
            return decoded_value.strip()
        except Exception as e:
            logger.error(f"Error decoding header: {str(e)}")
            return str(header_value).strip()

    def extract_emails_from_pdf(self, part):
        """Extract email addresses from PDF with improved error handling and memory management"""
        try:
            pdf_bytes = part.get_payload(decode=True)
            if not pdf_bytes:
                logger.warning("Empty PDF content")
                return []

            # Use context manager for proper resource cleanup
            with io.BytesIO(pdf_bytes) as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                
                text = ""
                for page_num, page in enumerate(pdf_reader.pages):
                    try:
                        text += page.extract_text() + "\n"
                    except Exception as e:
                        logger.error(f"Error extracting text from PDF page {page_num}: {str(e)}")
                        continue
                
                email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                emails = set(re.findall(email_pattern, text))
                logger.info(f"Found {len(emails)} email(s) in PDF")
                return list(emails)

        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return []

    def check_latest_email(self, mailbox="INBOX"):
        """Check latest email with improved IMAP handling and error recovery"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                if not self._ensure_selected_state():
                    raise Exception("Failed to select mailbox")
                    
                status, messages = self.imap.search(None, "ALL")
                if status != 'OK':
                    raise Exception(f"Failed to search messages: {messages}")
                    
                msg_nums = messages[0].split()
                if not msg_nums:
                    return True, {"message": "No emails found"}
                    
                latest_id = msg_nums[-1]
                status, msg_data = self.imap.fetch(latest_id, "(RFC822)")
                if status != 'OK':
                    raise Exception("Failed to fetch message")

                email_body = msg_data[0][1]
                message = email.message_from_bytes(email_body)

                # Parse email data
                subject = self._decode_email_header(message["subject"])
                sender = self._decode_email_header(message["from"])
                
                # Parse date with proper timezone handling
                date_str = message["date"]
                if date_str:
                    try:
                        parsed_date = parsedate_to_datetime(date_str)
                        utc = pytz.UTC
                        utc_date = parsed_date.astimezone(utc)
                        date = utc_date.strftime('%a, %d %b %Y %H:%M:%S %z')
                    except Exception as e:
                        logger.error(f"Date parsing error: {str(e)}")
                        date = datetime.now(pytz.UTC).strftime('%a, %d %b %Y %H:%M:%S %z')
                else:
                    date = datetime.now(pytz.UTC).strftime('%a, %d %b %Y %H:%M:%S %z')

                logger.info(f"Email details - Subject: {subject}, From: {sender}")

                # Process email content
                has_pdf = False
                pdf_emails = []
                
                for part in message.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue

                    filename = self._decode_email_header(part.get_filename())
                    content_type = part.get_content_type()

                    is_pdf = (
                        (filename and filename.lower().endswith('.pdf')) or
                        content_type in ['application/pdf', 'application/x-pdf']
                    )

                    if is_pdf:
                        has_pdf = True
                        logger.info(f"Found PDF attachment: {filename}")
                        pdf_emails = self.extract_emails_from_pdf(part)
                        break

                email_data = {
                    "subject": subject,
                    "from": sender,
                    "date": date,
                    "has_pdf": has_pdf,
                    "pdf_emails": pdf_emails
                }

                return True, email_data

            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {str(e)}")
                if attempt == max_retries - 1:
                    return False, {"error": str(e)}
                time.sleep(retry_delay * (attempt + 1))
                self._connect()  # Try reconnecting

    def test_connection(self):
        """Test IMAP connection with improved error reporting"""
        try:
            success, error = self._connect()
            if not success:
                return False, f"Connection failed: {error}"
            
            self._disconnect()
            return True, "Successfully connected to email server"
        except Exception as e:
            logger.error(f"Error testing connection: {str(e)}")
            return False, f"Error testing connection: {str(e)}"
