import csv
import os
from datetime import date, datetime
from io import BytesIO

import cv2
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.alert_manager import dispatch_alerts
from app.auth import authenticate, ensure_default_admin, get_role, login_response, logout_response, require_admin, require_login
from app.config import APP_NAME, CAMERA_LOCATION, CAMERA_NAME, CAMERA_URL
from app.database import Base, SessionLocal, engine, get_db, run_lightweight_migrations
from app.face_recognition_service import face_matcher
from app.models import Camera, RegisteredPerson, UnknownPerson, User, Violation
from app.vision import vision

Base.metadata.create_all(bind=engine)
run_lightweight_migrations()

with SessionLocal() as db:
    ensure_default_admin(db)
    if not db.query(Camera).first():
        db.add(Camera(camera_name=CAMERA_NAME, camera_url=CAMERA_URL, location=CAMERA_LOCATION, is_active=True))
        db.commit()

app = FastAPI(title=APP_NAME)
templates = Jinja2Templates(directory="templates")

for folder in ["snapshots", "static", "known_faces", "reports"]:
    os.makedirs(folder, exist_ok=True)

app.mount("/snapshots", StaticFiles(directory="snapshots"), name="snapshots")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/known_faces", StaticFiles(directory="known_faces"), name="known_faces")

camera = None
active_camera_url = CAMERA_URL


def template_context(request: Request, db: Session, user_id: str, **extra):
    context = {
        "request": request,
        "app_name": APP_NAME,
        "user": user_id,
        "role": get_role(db, user_id),
    }
    context.update(extra)
    return context


def open_camera(camera_url: str | None = None):
    global camera, active_camera_url
    selected_url = camera_url or active_camera_url

    if camera is None or not camera.isOpened() or selected_url != active_camera_url:
        if camera is not None:
            camera.release()
        active_camera_url = selected_url
        source = int(selected_url) if str(selected_url).isdigit() else selected_url
        camera = cv2.VideoCapture(source)

    return camera


def selected_camera(db: Session):
    camera_row = db.query(Camera).filter(Camera.is_active == True).first()  # noqa: E712
    if camera_row:
        return camera_row
    return Camera(id=None, camera_name=CAMERA_NAME, camera_url=CAMERA_URL, location=CAMERA_LOCATION, is_active=True)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "app_name": APP_NAME})


@app.post("/login")
def login(user_id: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate(db, user_id, password)
    if not user:
        return RedirectResponse("/login?error=1", status_code=302)
    return login_response("/", user.user_id)


@app.get("/logout")
def logout():
    return logout_response()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, user=Depends(require_login), db: Session = Depends(get_db)):
    today_start = datetime.combine(date.today(), datetime.min.time())
    camera_row = selected_camera(db)
    vision.use_camera(camera_row.id, camera_row.camera_name, camera_row.location)

    return templates.TemplateResponse(
        "dashboard.html",
        template_context(
            request,
            db,
            user,
            camera_name=camera_row.camera_name,
            camera_location=camera_row.location,
            total_violations=db.query(Violation).count(),
            today_violations=db.query(Violation).filter(Violation.timestamp >= today_start).count(),
            people_count=db.query(RegisteredPerson).filter(RegisteredPerson.active == True).count(),  # noqa: E712
            unknown_count=db.query(UnknownPerson).count(),
            repeat_count=db.query(Violation).filter(Violation.repeat_count > 1).count(),
            recent=db.query(Violation).order_by(Violation.timestamp.desc()).limit(10).all(),
        ),
    )


@app.get("/operator", response_class=HTMLResponse)
def operator_panel(request: Request, user=Depends(require_login), db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        "operator_panel.html",
        template_context(
            request,
            db,
            user,
            recent=db.query(Violation).order_by(Violation.timestamp.desc()).limit(20).all(),
        ),
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request, user=Depends(require_login), db: Session = Depends(get_db)):
    require_admin(request, db)
    return templates.TemplateResponse(
        "admin_panel.html",
        template_context(
            request,
            db,
            user,
            users=db.query(User).order_by(User.id.desc()).all(),
            cameras=db.query(Camera).order_by(Camera.id.desc()).all(),
            persons=db.query(RegisteredPerson).order_by(RegisteredPerson.id.desc()).limit(8).all(),
        ),
    )


@app.post("/admin/users/add")
def add_user(
    request: Request,
    user_id: str = Form(...),
    password: str = Form(...),
    role: str = Form("operator"),
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    require_admin(request, db)
    if db.query(User).filter(User.user_id == user_id).first():
        return RedirectResponse("/admin?error=user_exists", status_code=302)
    db.add(User(user_id=user_id.strip(), password=password.strip(), role=role, active=True))
    db.commit()
    return RedirectResponse("/admin", status_code=302)


@app.get("/persons", response_class=HTMLResponse)
def persons_page(request: Request, user=Depends(require_login), db: Session = Depends(get_db)):
    persons = db.query(RegisteredPerson).order_by(RegisteredPerson.id.desc()).all()
    return templates.TemplateResponse("persons.html", template_context(request, db, user, persons=persons, edit_person=None))


@app.get("/persons/edit/{person_id}", response_class=HTMLResponse)
def edit_person_page(person_id: int, request: Request, user=Depends(require_login), db: Session = Depends(get_db)):
    person = db.query(RegisteredPerson).get(person_id)
    if not person:
        raise HTTPException(404)
    persons = db.query(RegisteredPerson).order_by(RegisteredPerson.id.desc()).all()
    return templates.TemplateResponse("persons.html", template_context(request, db, user, persons=persons, edit_person=person))


@app.post("/persons/save")
def save_person(
    person_id: int = Form(0),
    person_code: str = Form(...),
    name: str = Form(...),
    department: str = Form(""),
    designation: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    notes: str = Form(""),
    active: str = Form("1"),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    person = db.query(RegisteredPerson).get(person_id) if person_id else RegisteredPerson()
    if not person:
        raise HTTPException(404)

    clean_name = name.strip()
    person.person_code = person_code.strip()
    person.name = clean_name
    person.department = department.strip()
    person.designation = designation.strip()
    person.email = email.strip()
    person.phone = phone.strip()
    person.notes = notes.strip()
    person.active = active == "1"
    person.updated_at = datetime.utcnow()

    if photo and photo.filename:
        folder_name = clean_name.replace(" ", "_")
        folder = os.path.join("known_faces", folder_name)
        os.makedirs(folder, exist_ok=True)
        safe_file_name = f"{int(datetime.utcnow().timestamp())}_{photo.filename}"
        face_path = os.path.join(folder, safe_file_name)
        with open(face_path, "wb") as file:
            file.write(photo.file.read())
        person.face_image_path = face_path

    db.add(person)
    db.commit()
    face_matcher.reload()
    return RedirectResponse("/persons", status_code=302)


@app.get("/persons/delete/{person_id}")
def delete_person(person_id: int, db: Session = Depends(get_db), user=Depends(require_login)):
    person = db.query(RegisteredPerson).get(person_id)
    if person:
        db.delete(person)
        db.commit()
        face_matcher.reload()
    return RedirectResponse("/persons", status_code=302)


@app.get("/violations", response_class=HTMLResponse)
def violations_page(
    request: Request,
    q: str = "",
    camera_name: str = "",
    person_type: str = "",
    from_date: str = "",
    to_date: str = "",
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    query = db.query(Violation)

    if q:
        like_value = f"%{q}%"
        query = query.filter(or_(Violation.person_name.like(like_value), Violation.person_code.like(like_value), Violation.violation_id.like(like_value)))
    if camera_name:
        query = query.filter(Violation.camera_name == camera_name)
    if person_type == "known":
        query = query.filter(Violation.is_unknown == False)  # noqa: E712
    if person_type == "unknown":
        query = query.filter(Violation.is_unknown == True)  # noqa: E712
    if from_date:
        query = query.filter(Violation.timestamp >= datetime.fromisoformat(from_date))
    if to_date:
        query = query.filter(Violation.timestamp < datetime.fromisoformat(to_date))

    violations = query.order_by(Violation.timestamp.desc()).all()
    cameras = [item[0] for item in db.query(Violation.camera_name).distinct().all() if item[0]]
    return templates.TemplateResponse(
        "violations.html",
        template_context(
            request,
            db,
            user,
            violations=violations,
            cameras=cameras,
            filters={"q": q, "camera_name": camera_name, "person_type": person_type, "from_date": from_date, "to_date": to_date},
        ),
    )


@app.get("/violations/{violation_id}", response_class=HTMLResponse)
def violation_detail(violation_id: str, request: Request, db: Session = Depends(get_db), user=Depends(require_login)):
    violation = db.query(Violation).filter(Violation.violation_id == violation_id).first()
    if not violation:
        raise HTTPException(404)

    history = []
    if violation.person_code:
        history = db.query(Violation).filter(Violation.person_code == violation.person_code).order_by(Violation.timestamp.desc()).all()
    elif violation.unknown_tracking_id:
        history = db.query(Violation).filter(Violation.unknown_tracking_id == violation.unknown_tracking_id).order_by(Violation.timestamp.desc()).all()

    return templates.TemplateResponse("violation_detail.html", template_context(request, db, user, v=violation, history=history))


@app.get("/violations/{violation_id}/resend")
def resend_alert(violation_id: str, db: Session = Depends(get_db), user=Depends(require_login)):
    dispatch_alerts(db, violation_id)
    return RedirectResponse(f"/violations/{violation_id}", status_code=302)


@app.get("/cameras", response_class=HTMLResponse)
def cameras_page(request: Request, user=Depends(require_login), db: Session = Depends(get_db)):
    return templates.TemplateResponse("cameras.html", template_context(request, db, user, cameras=db.query(Camera).order_by(Camera.id.desc()).all()))


@app.post("/cameras/save")
def save_camera(
    camera_name: str = Form(...),
    camera_url: str = Form("0"),
    location: str = Form(""),
    db: Session = Depends(get_db),
    user=Depends(require_login),
):
    db.add(Camera(camera_name=camera_name.strip(), camera_url=camera_url.strip(), location=location.strip(), is_active=False))
    db.commit()
    return RedirectResponse("/cameras", status_code=302)


@app.get("/cameras/activate/{camera_id}")
def activate_camera(camera_id: int, db: Session = Depends(get_db), user=Depends(require_login)):
    for camera_row in db.query(Camera).all():
        camera_row.is_active = camera_row.id == camera_id
        db.add(camera_row)
    db.commit()
    active = db.query(Camera).get(camera_id)
    if active:
        vision.use_camera(active.id, active.camera_name, active.location)
        open_camera(active.camera_url)
    return RedirectResponse("/cameras", status_code=302)


@app.get("/cameras/delete/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db), user=Depends(require_login)):
    camera_row = db.query(Camera).get(camera_id)
    if camera_row and not camera_row.is_active:
        db.delete(camera_row)
        db.commit()
    return RedirectResponse("/cameras", status_code=302)


def frame_generator():
    with SessionLocal() as db:
        camera_row = selected_camera(db)
    cap = open_camera(camera_row.camera_url)

    while True:
        ok, frame = cap.read()
        if not ok:
            import numpy as np

            frame = 255 * np.ones((480, 800, 3), dtype="uint8")
            cv2.putText(frame, "Camera not available. Check camera settings.", (35, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        with SessionLocal() as db:
            camera_row = selected_camera(db)
            vision.use_camera(camera_row.id, camera_row.camera_name, camera_row.location)
            annotated, violations = vision.process_frame(frame, db)
            for item in violations:
                dispatch_alerts(db, item["violation_id"])

        ready, buffer = cv2.imencode(".jpg", annotated)
        if ready:
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"


@app.get("/video_feed")
def video_feed(user=Depends(require_login)):
    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/live_counts")
def live_counts(user=Depends(require_login)):
    return {
        "people": vision.live_people,
        "vehicles": vision.live_vehicles,
        "no_helmets": vision.live_no_helmet,
        "identity": vision.last_identity,
        "model_ready": vision.model_ready,
        "camera": vision.camera_name,
        "location": vision.location,
    }


def filtered_report_rows(db: Session):
    return db.query(Violation).order_by(Violation.timestamp.desc()).all()


@app.get("/api/reports/csv")
def report_csv(db: Session = Depends(get_db), user=Depends(require_login)):
    path = os.path.join("reports", "violations_report.csv")
    rows = filtered_report_rows(db)

    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Violation ID", "Person", "Person Code", "Department", "Helmet", "Camera", "Location", "Date Time", "Confidence", "Repeat Count", "Email", "SMS", "Status"])
        for row in rows:
            writer.writerow([
                row.violation_id,
                row.person_name,
                row.person_code or "",
                row.department or "",
                row.helmet_status,
                row.camera_name,
                row.location,
                row.timestamp.strftime("%d-%m-%Y %H:%M:%S"),
                row.confidence_score,
                row.repeat_count,
                "Sent" if row.email_sent else "No",
                "Sent" if row.sms_sent else "No",
                row.status,
            ])

    return FileResponse(path, filename="violations_report.csv")


@app.get("/api/reports/pdf")
def report_pdf(db: Session = Depends(get_db), user=Depends(require_login)):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except Exception:
        raise HTTPException(status_code=500, detail="Install reportlab first: pip install reportlab")

    path = os.path.join("reports", "violations_report.pdf")
    document = SimpleDocTemplate(path, pagesize=landscape(A4))
    styles = getSampleStyleSheet()
    story = [Paragraph("JK Paper Helmet Violation Report", styles["Title"]), Spacer(1, 12)]

    data = [["ID", "Person", "Code", "Dept", "Camera", "Date/Time", "Repeat", "Status"]]
    for row in filtered_report_rows(db):
        data.append([
            row.violation_id,
            row.person_name,
            row.person_code or "-",
            row.department or "-",
            row.camera_name,
            row.timestamp.strftime("%d-%m-%Y %H:%M"),
            str(row.repeat_count),
            row.status,
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0B5D3B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    document.build(story)
    return FileResponse(path, filename="violations_report.pdf")
