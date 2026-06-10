# JK Helmet Violation Digital Management System - Pro

This ZIP continues the existing FastAPI + SQLite + YOLO project. It does **not** rebuild the project from scratch.

## Added / Upgraded Features

- Premium JK Paper corporate dashboard UI
- Mobile responsive layout
- Add / edit / delete registered persons
- Department and designation fields for registered persons
- Live person identification display
- Real no-helmet workflow with snapshot + database record
- Violation details page with repeat history
- Email alert with snapshot attachment
- Twilio SMS alert support
- Search and filter violations
- CSV report export
- PDF report export using ReportLab
- Multi-camera management
- Admin panel
- Operator panel
- Unknown person tracking
- Repeat offender count
- LAN deployment-ready command

## Default Login

```text
User ID : admin
Password: admin123
```

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

Then open from another device on the same Wi-Fi:

```text
http://YOUR_LAPTOP_IP:8000
```

## YOLO Model Setup

Place the trained helmet model here:

```text
backend/models/best.pt
```

Your model should ideally contain class names similar to:

```text
helmet
no_helmet
person
motorcycle
```

The workflow logs violations only when a `no_helmet` style class is detected.

## Email / SMS Setup

Edit:

```text
backend/.env
```

Required values:

```text
OPERATOR_EMAIL=
OPERATOR_PHONE=
SMTP_USER=
SMTP_PASSWORD=
SMS_API_KEY=
SMS_API_SECRET=
SMS_SENDER_ID=
```

For Gmail SMTP, use an app password instead of your normal Gmail password.

## Notes

- Existing structure is preserved.
- SQLite migrations are handled inside `database.py` using a small helper.
- The current face matcher is still lightweight and demo-friendly. For production-level accuracy, replace it later with DeepFace, InsightFace, or face_recognition.
