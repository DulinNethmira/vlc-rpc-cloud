from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
import uuid
import hashlib
from datetime import datetime, timezone, timedelta

from database import get_db
from models import User, RefreshToken, Installation
from auth import (
    verify_password, get_password_hash, 
    create_access_token, create_refresh_token, 
    decode_token, REFRESH_TOKEN_EXPIRE_DAYS
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

class AuthRequest(BaseModel):
    email: str
    password: str
    installation_id: str = None # Optional linking

class RefreshRequest(BaseModel):
    refresh_token: str

@router.post("/register")
def register(req: AuthRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=req.email,
        password_hash=get_password_hash(req.password)
    )
    db.add(user)
    db.commit()

    if req.installation_id:
        try:
            inst_uuid = uuid.UUID(req.installation_id)
            inst = db.query(Installation).filter(Installation.id == inst_uuid).first()
            if inst:
                inst.user_id = user.id
                db.commit()
        except ValueError:
            pass

    return {"status": "registered"}

@router.post("/login")
def login(req: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if req.installation_id:
        try:
            inst_uuid = uuid.UUID(req.installation_id)
            inst = db.query(Installation).filter(Installation.id == inst_uuid).first()
            if inst:
                inst.user_id = user.id
                db.commit()
        except ValueError:
            pass

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    
    # Store refresh token server-side for revocation
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    db_token = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at
    )
    db.add(db_token)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/logout")
def logout(req: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    
    if db_token:
        db_token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        
    return {"status": "logged_out"}

@router.post("/refresh")
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(req.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    db_token = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    
    if not db_token or db_token.revoked_at is not None:
        raise HTTPException(status_code=401, detail="Token revoked")
        
    user_id = payload.get("sub")
    access_token = create_access_token({"sub": user_id})
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    try:
        user_uuid = uuid.UUID(payload.get("sub"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid user ID in token")
        
    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

@router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}

@router.get("/devices")
def get_devices(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    installations = db.query(Installation).filter(Installation.user_id == current_user.id).all()
    return [{"id": inst.id, "app_version": inst.app_version, "platform": inst.platform, "last_seen": inst.last_seen} for inst in installations]

@router.delete("/devices/{installation_id}")
def revoke_device(installation_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        inst_uuid = uuid.UUID(installation_id)
        inst = db.query(Installation).filter(Installation.id == inst_uuid, Installation.user_id == current_user.id).first()
        if not inst:
            raise HTTPException(status_code=404, detail="Installation not found")
        
        inst.user_id = None
        db.commit()
        return {"status": "revoked"}
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid installation ID")
