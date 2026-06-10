import os
import time
from datetime import datetime

import cv2
from sqlalchemy.orm import Session

from app.config import ALERT_COOLDOWN_SECONDS, CAMERA_LOCATION, CAMERA_NAME, MODEL_PATH
from app.face_recognition_service import face_matcher
from app.models import RegisteredPerson, UnknownPerson, Violation

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None


class VisionPipeline:
    """Runs the live camera workflow.

    The code is intentionally readable: detect helmet status, identify the person,
    save a snapshot, then store one violation record after cooldown.
    """

    def __init__(self):
        self.camera_name = CAMERA_NAME
        self.location = CAMERA_LOCATION
        self.camera_id = None
        self.snapshot_dir = "snapshots"
        os.makedirs(self.snapshot_dir, exist_ok=True)

        self.model = None
        self.model_ready = False
        self.last_violation_time = 0

        self.live_people = 0
        self.live_vehicles = 0
        self.live_no_helmet = 0
        self.last_identity = "Unknown"
        self.last_camera_status = "Starting"

        self.load_model()

    def load_model(self):
        if YOLO is None:
            print("Ultralytics is not installed. YOLO detection is disabled.")
            return

        model_path = MODEL_PATH if os.path.exists(MODEL_PATH) else "yolov8n.pt"
        try:
            self.model = YOLO(model_path)
            self.model_ready = True
            print("YOLO model loaded:", model_path)
        except Exception as error:
            print("Model load failed:", error)
            self.model_ready = False

    def use_camera(self, camera_id, camera_name: str, location: str):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.location = location

    def _save_snapshot(self, frame):
        file_name = f"violation_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
        path = os.path.join(self.snapshot_dir, file_name)
        cv2.imwrite(path, frame)
        return path

    def _find_registered_person(self, db: Session, matched_name: str):
        if matched_name == "Unknown":
            return None
        return db.query(RegisteredPerson).filter(RegisteredPerson.name == matched_name, RegisteredPerson.active == True).first()  # noqa: E712

    def _repeat_count_for_known_person(self, db: Session, person_code: str | None):
        if not person_code:
            return 1
        return db.query(Violation).filter(Violation.person_code == person_code).count() + 1

    def _update_unknown_tracking(self, db: Session, snapshot_path: str):
        latest_unknown = db.query(UnknownPerson).order_by(UnknownPerson.last_seen.desc()).first()
        now = datetime.utcnow()

        # Simple tracking baseline: if the last unknown was seen recently, continue the same ID.
        if latest_unknown and (now - latest_unknown.last_seen).total_seconds() < 300:
            latest_unknown.last_seen = now
            latest_unknown.last_snapshot_path = snapshot_path
            latest_unknown.violation_count += 1
            db.commit()
            return latest_unknown.tracking_id, latest_unknown.violation_count

        tracking_id = f"UNK-{now.strftime('%Y%m%d-%H%M%S')}"
        unknown = UnknownPerson(
            tracking_id=tracking_id,
            first_snapshot_path=snapshot_path,
            last_snapshot_path=snapshot_path,
            camera_name=self.camera_name,
            location=self.location,
            first_seen=now,
            last_seen=now,
            violation_count=1,
        )
        db.add(unknown)
        db.commit()
        return tracking_id, 1

    def _record_violation(self, db: Session, annotated_frame, name: str, face_score: float, confidence: float):
        snapshot_path = self._save_snapshot(annotated_frame)
        violation_id = "VIO-" + time.strftime("%Y%m%d-%H%M%S")
        person = self._find_registered_person(db, name)

        if person:
            repeat_count = self._repeat_count_for_known_person(db, person.person_code)
            violation = Violation(
                violation_id=violation_id,
                person_name=person.name,
                person_code=person.person_code,
                department=person.department or "",
                designation=person.designation or "",
                camera_id=self.camera_id,
                camera_name=self.camera_name,
                location=self.location,
                confidence_score=float(confidence),
                face_score=float(face_score),
                snapshot_path=snapshot_path,
                helmet_status="NO_HELMET",
                is_unknown=False,
                repeat_count=repeat_count,
            )
        else:
            tracking_id, repeat_count = self._update_unknown_tracking(db, snapshot_path)
            violation = Violation(
                violation_id=violation_id,
                person_name="Unknown",
                person_code=None,
                camera_id=self.camera_id,
                camera_name=self.camera_name,
                location=self.location,
                confidence_score=float(confidence),
                face_score=float(face_score),
                snapshot_path=snapshot_path,
                helmet_status="NO_HELMET",
                is_unknown=True,
                unknown_tracking_id=tracking_id,
                repeat_count=repeat_count,
            )

        db.add(violation)
        db.commit()
        return {"violation_id": violation_id, "person": violation.person_name, "confidence": confidence}

    def process_frame(self, frame, db: Session = None):
        annotated = frame.copy()
        violations = []
        self.live_people = 0
        self.live_vehicles = 0
        self.live_no_helmet = 0

        name, face_score = face_matcher.match(frame)
        self.last_identity = name
        cv2.putText(annotated, f"Identity: {name}", (20, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 255), 2)

        if not self.model_ready:
            cv2.putText(annotated, "Model missing: add backend/models/best.pt", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return annotated, violations

        try:
            result = self.model(annotated, verbose=False)[0]
            model_names = self.model.names
            no_helmet_found = False
            best_no_helmet_confidence = 0.0

            for box in result.boxes:
                class_id = int(box.cls[0])
                confidence = float(box.conf[0])
                label = str(model_names.get(class_id, class_id)).lower().replace("-", "_").replace(" ", "_")
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                color = (120, 120, 120)
                text = f"{label} {confidence:.2f}"

                if label in ["person", "rider"]:
                    self.live_people += 1
                    color = (255, 165, 0)
                elif label in ["motorcycle", "motorbike", "bike", "bicycle"]:
                    self.live_vehicles += 1
                    color = (255, 255, 0)
                elif label in ["no_helmet", "nohelmet", "without_helmet", "no_helmet_detected"]:
                    self.live_no_helmet += 1
                    no_helmet_found = True
                    best_no_helmet_confidence = max(best_no_helmet_confidence, confidence)
                    color = (0, 0, 255)
                    text = f"NO HELMET {confidence:.2f}"
                elif label in ["helmet", "with_helmet"]:
                    color = (0, 255, 0)
                    text = f"Helmet {confidence:.2f}"
                else:
                    continue

                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(annotated, text, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

            cooldown_over = time.time() - self.last_violation_time > ALERT_COOLDOWN_SECONDS
            if no_helmet_found and db and cooldown_over:
                self.last_violation_time = time.time()
                violations.append(self._record_violation(db, annotated, name, face_score, best_no_helmet_confidence))

        except Exception as error:
            cv2.putText(annotated, f"Detection error: {error}", (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        return annotated, violations


vision = VisionPipeline()
