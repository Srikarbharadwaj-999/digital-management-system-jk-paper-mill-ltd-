import os
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import (
    OPERATOR_EMAIL,
    OPERATOR_PHONE,
    SMS_API_KEY,
    SMS_API_SECRET,
    SMS_PROVIDER,
    SMS_SENDER_ID,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)
from app.models import AlertLog, Violation


def _snapshot_file(path: str | None):
    if not path:
        return None
    if os.path.exists(path):
        return path
    cleaned = os.path.basename(path)
    candidate = os.path.join("snapshots", cleaned)
    return candidate if os.path.exists(candidate) else None


def send_email_alert(violation: Violation):
    if not SMTP_USER or not SMTP_PASSWORD or not OPERATOR_EMAIL:
        return False, "SMTP or operator email not configured"

    try:
        message = EmailMessage()
        message["Subject"] = f"Helmet Violation Alert - {violation.violation_id}"
        message["From"] = SMTP_USER
        message["To"] = OPERATOR_EMAIL
        message.set_content(
            f"""
JK Paper Helmet Violation Alert

Violation ID : {violation.violation_id}
Person       : {violation.person_name}
Employee ID  : {violation.person_code or 'N/A'}
Department   : {violation.department or 'N/A'}
Camera       : {violation.camera_name}
Location     : {violation.location}
Helmet Status: {violation.helmet_status}
Time         : {violation.timestamp.strftime('%d-%m-%Y %H:%M:%S')}
Confidence   : {round(violation.confidence_score or 0, 2)}
Repeat Count : {violation.repeat_count}

Snapshot is attached when available.
""".strip()
        )

        snapshot_path = _snapshot_file(violation.snapshot_path)
        if snapshot_path:
            with open(snapshot_path, "rb") as snapshot:
                message.add_attachment(
                    snapshot.read(),
                    maintype="image",
                    subtype="jpeg",
                    filename=os.path.basename(snapshot_path),
                )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(message)

        return True, None
    except Exception as error:
        return False, str(error)


def send_sms_alert(violation: Violation):
    if SMS_PROVIDER.lower() != "twilio":
        return False, "SMS provider is not Twilio"
    if not SMS_API_KEY or not SMS_API_SECRET or not SMS_SENDER_ID or not OPERATOR_PHONE:
        return False, "Twilio or operator phone not configured"

    try:
        from twilio.rest import Client

        body = (
            f"JK Helmet Alert: {violation.person_name} "
            f"({violation.person_code or 'Unknown'}) at {violation.location}. "
            f"Camera: {violation.camera_name}. "
            f"Time: {violation.timestamp.strftime('%d-%m-%Y %H:%M:%S')}"
        )
        Client(SMS_API_KEY, SMS_API_SECRET).messages.create(
            body=body,
            from_=SMS_SENDER_ID,
            to=OPERATOR_PHONE,
        )
        return True, None
    except Exception as error:
        return False, str(error)


def dispatch_alerts(db: Session, violation_id: str):
    violation = db.query(Violation).filter(Violation.violation_id == violation_id).first()
    if not violation:
        return None

    email_ok, email_error = send_email_alert(violation)
    sms_ok, sms_error = send_sms_alert(violation)

    violation.email_sent = email_ok
    violation.email_error = email_error
    violation.sms_sent = sms_ok
    violation.sms_error = sms_error
    violation.status = "Alert Sent" if email_ok or sms_ok else "Saved"

    db.add(AlertLog(violation_id=violation.violation_id, alert_type="email", recipient=OPERATOR_EMAIL, success=email_ok, error=email_error))
    db.add(AlertLog(violation_id=violation.violation_id, alert_type="sms", recipient=OPERATOR_PHONE, success=sms_ok, error=sms_error))
    db.commit()
    return violation
