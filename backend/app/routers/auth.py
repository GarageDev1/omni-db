from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.deps import get_db, get_current_user
from app.schemas.auth import LoginRequest, TokenResponse, RegisterRequest, PasswordChangeRequest, CasdoorCallbackRequest
from app.schemas.user import UserOut
from app.services.auth_service import authenticate_user, create_access_token, hash_password, verify_password
from app.services import casdoor_service
from app.models.user import User
import uuid

router = APIRouter()

@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user.id, "role": user.role})
    return {"data": {"access_token": token, "token_type": "bearer"}, "message": "ok"}

@router.get("/casdoor/config")
def casdoor_config():
    return {"data": casdoor_service.public_config(), "message": "ok"}

@router.get("/casdoor/login-url")
def casdoor_login_url(state: str | None = None, redirect_uri: str | None = None):
    try:
        login_url = casdoor_service.build_authorization_url(state=state, redirect_uri=redirect_uri)
    except casdoor_service.CasdoorAuthError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"data": {"url": login_url}, "message": "ok"}

@router.post("/casdoor/callback")
def casdoor_callback(body: CasdoorCallbackRequest, db: Session = Depends(get_db)):
    try:
        user = casdoor_service.exchange_code_and_sync_user(
            db,
            code=body.code,
            redirect_uri=body.redirect_uri,
        )
    except casdoor_service.CasdoorAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    token = create_access_token({"sub": user.id, "role": user.role})
    return {"data": {"access_token": token, "token_type": "bearer"}, "message": "ok"}

@router.post("/register", status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter((User.username == body.username) | (User.email == body.email)).first():
        raise HTTPException(status_code=409, detail="Username or email already exists")
    user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role="viewer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"data": UserOut.model_validate(user).model_dump(), "message": "ok"}

@router.get("/profile")
def profile(current_user: User = Depends(get_current_user)):
    return {"data": UserOut.model_validate(current_user).model_dump(), "message": "ok"}

@router.put("/password")
def change_password(body: PasswordChangeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    current_user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"message": "Password updated"}
