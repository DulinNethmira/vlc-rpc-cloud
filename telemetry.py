from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
import uuid
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel

from database import get_db
from models import Installation, DailyInstallationActivity

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

class RegisterRequest(BaseModel):
    installation_id: str
    app_version: str
    platform: str

class HeartbeatRequest(BaseModel):
    installation_id: str

@router.post("/register")
def register_installation(req: RegisterRequest, db: Session = Depends(get_db)):
    try:
        install_uuid = uuid.UUID(req.installation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid installation_id")

    installation = db.query(Installation).filter(Installation.id == install_uuid).first()
    if not installation:
        installation = Installation(
            id=install_uuid,
            app_version=req.app_version,
            platform=req.platform
        )
        db.add(installation)
        db.commit()
    else:
        # Update version/platform if changed
        if installation.app_version != req.app_version or installation.platform != req.platform:
            installation.app_version = req.app_version
            installation.platform = req.platform
            db.commit()

    return {"status": "registered"}

@router.post("/heartbeat")
def heartbeat(req: HeartbeatRequest, db: Session = Depends(get_db)):
    try:
        install_uuid = uuid.UUID(req.installation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid installation_id")

    installation = db.query(Installation).filter(Installation.id == install_uuid).first()
    if not installation:
        raise HTTPException(status_code=404, detail="Installation not found")

    now = datetime.now(timezone.utc)
    
    # DB Efficiency: only update last_seen if it's older than 2 minutes
    # Handle timezone naive vs aware correctly
    last_seen = installation.last_seen
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
        
    if (now - last_seen) > timedelta(minutes=2):
        installation.last_seen = now
        
        # We need to record daily activity idempotently.
        # SQLite doesn't natively support ON CONFLICT DO NOTHING with the same syntax as postgres,
        # but SQLAlchemy's insert statement provides support.
        # For cross-compatibility with SQLite during local dev, we will just use a simple approach:
        today = now.date()
        
        existing_activity = db.query(DailyInstallationActivity).filter(
            DailyInstallationActivity.date == today,
            DailyInstallationActivity.installation_id == install_uuid
        ).first()
        
        if not existing_activity:
            try:
                activity = DailyInstallationActivity(date=today, installation_id=install_uuid)
                db.add(activity)
                db.commit()
            except Exception:
                # If there is a race condition resulting in a unique constraint failure, rollback
                db.rollback()
        else:
            db.commit() # Commit the last_seen update

    return {"status": "ok"}

from auth_router import get_current_user
from models import User, DailyUsage
from sqlalchemy import func

@router.get("/admin/stats")
def admin_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Real-time stats
    now = datetime.now(timezone.utc)
    five_mins_ago = now - timedelta(minutes=5)

    online_now = db.query(func.count(Installation.id)).filter(Installation.last_seen >= five_mins_ago).scalar()
    
    today = now.date()
    daily_active = db.query(func.count(DailyInstallationActivity.installation_id)).filter(
        DailyInstallationActivity.date == today
    ).scalar()

    total_installations = db.query(func.count(Installation.id)).scalar()
    total_users = db.query(func.count(User.id)).scalar()

    return {
        "online_now": online_now,
        "daily_active_installations": daily_active,
        "total_installations": total_installations,
        "total_registered_users": total_users,
        "timestamp": now.isoformat()
    }
