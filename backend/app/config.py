import os
from dotenv import load_dotenv
load_dotenv()

APP_NAME = os.getenv("APP_NAME", "JK Helmet Violation DMS")
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret")
MODEL_PATH = os.getenv("MODEL_PATH", "models/best.pt")
CAMERA_URL = os.getenv("CAMERA_URL", "0")
CAMERA_NAME = os.getenv("CAMERA_NAME", "Main Gate Camera")
CAMERA_LOCATION = os.getenv("CAMERA_LOCATION", "Main Gate")
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "30"))

OPERATOR_EMAIL = os.getenv("OPERATOR_EMAIL", "operator@example.com")
OPERATOR_PHONE = os.getenv("OPERATOR_PHONE", "+910000000000")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMS_PROVIDER = os.getenv("SMS_PROVIDER", "twilio")
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
SMS_API_SECRET = os.getenv("SMS_API_SECRET", "")
SMS_SENDER_ID = os.getenv("SMS_SENDER_ID", "")
