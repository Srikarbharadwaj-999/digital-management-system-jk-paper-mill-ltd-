from datetime import datetime

from app.database import Base
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="operator")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class RegisteredPerson(Base):
    __tablename__ = "registered_persons"

    id = Column(Integer, primary_key=True, index=True)
    person_code = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    department = Column(String, default="")
    designation = Column(String, default="")
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    face_image_path = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    camera_name = Column(String, nullable=False)
    camera_url = Column(String, default="0")
    location = Column(String, default="Main Gate")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    violation_id = Column(String, unique=True, index=True)
    person_name = Column(String, default="Unknown")
    person_code = Column(String, nullable=True)
    department = Column(String, default="")
    designation = Column(String, default="")
    helmet_status = Column(String, default="NO_HELMET")
    camera_name = Column(String, index=True)
    camera_id = Column(Integer, nullable=True)
    location = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    confidence_score = Column(Float)
    face_score = Column(Float, default=0.0)
    snapshot_path = Column(String)
    is_unknown = Column(Boolean, default=True)
    unknown_tracking_id = Column(String, nullable=True)
    repeat_count = Column(Integer, default=1)
    email_sent = Column(Boolean, default=False)
    sms_sent = Column(Boolean, default=False)
    email_error = Column(String, nullable=True)
    sms_error = Column(String, nullable=True)
    status = Column(String, default="Pending")


class UnknownPerson(Base):
    __tablename__ = "unknown_persons"

    id = Column(Integer, primary_key=True, index=True)
    tracking_id = Column(String, unique=True, index=True)
    first_snapshot_path = Column(String, nullable=True)
    last_snapshot_path = Column(String, nullable=True)
    camera_name = Column(String, default="")
    location = Column(String, default="")
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    violation_count = Column(Integer, default=1)


class AlertLog(Base):
    __tablename__ = "alert_logs"

    id = Column(Integer, primary_key=True, index=True)
    violation_id = Column(String, index=True)
    alert_type = Column(String)
    recipient = Column(String)
    success = Column(Boolean, default=False)
    error = Column(String, nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
