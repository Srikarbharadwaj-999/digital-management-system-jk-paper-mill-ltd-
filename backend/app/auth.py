from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.models import User

SESSION_COOKIE = "jk_dms_user"


def ensure_default_admin(db: Session):
    admin = db.query(User).filter(User.user_id == "admin").first()
    if not admin:
        db.add(User(user_id="admin", password="admin123", role="admin", active=True))
        db.commit()


def authenticate(db: Session, user_id: str, password: str):
    return (
        db.query(User)
        .filter(User.user_id == user_id, User.password == password, User.active == True)  # noqa: E712
        .first()
    )


def current_user_id(request: Request):
    return request.cookies.get(SESSION_COOKIE)


def require_login(request: Request):
    user_id = current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user_id


def require_admin(request: Request, db: Session):
    user_id = require_login(request)
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


def get_role(db: Session, user_id: str) -> str:
    user = db.query(User).filter(User.user_id == user_id).first()
    return user.role if user else "operator"


def login_response(url: str, user_id: str):
    response = RedirectResponse(url=url, status_code=302)
    response.set_cookie(SESSION_COOKIE, user_id, httponly=True, max_age=60 * 60 * 8)
    return response


def logout_response():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response
