# JK Helmet Violation Digital Management System

A FastAPI, SQLite, and YOLO-based digital management system for detecting and managing helmet violations in an industrial environment.

## Key Features

* Corporate-style responsive dashboard UI
* Registered person management
* Add, edit, and delete registered persons
* Department and designation details
* Live person identification display
* No-helmet detection workflow
* Violation snapshot capture
* Violation database records
* Violation details page
* Repeat offender tracking
* Unknown person tracking
* Search and filter violations
* CSV report export
* PDF report export
* Multi-camera management
* Admin panel
* Operator panel
* Email alert support
* SMS alert support
* LAN deployment support

## Default Login

User ID: admin
Password: admin123

## Run on Windows

```cmd
cd HelmetViolationSystem_Pro\backend
py -3.11 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## LAN Access

```cmd
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open from another device on the same Wi-Fi:

```text
http://YOUR_LAPTOP_IP:8000
```

## YOLO Model Setup

Place the trained helmet detection model here:

```text
backend/models/best.pt
```

Recommended class names:

```text
helmet
no_helmet
person
motorcycle
```

The system logs a violation when a no-helmet class is detected.

## Alert Configuration

Update environment variables in:

```text
backend/.env
```

Required configuration values:

```text
OPERATOR_EMAIL=
OPERATOR_PHONE=
SMTP_USER=
SMTP_PASSWORD
```

For Gmail SMTP, use an app password instead of a normal Gmail password.

## Notes

* Existing project structure is preserved.
* SQLite migration handling is included in `database.py`.
* The current face matching module is lightweight and suitable for demonstration.
* For production-level accuracy, future upgrades may include DeepFace, InsightFace, or face_recognition.
