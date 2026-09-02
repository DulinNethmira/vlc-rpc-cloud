from sqlalchemy import Boolean, Column, String, Integer, Date, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    installations = relationship("Installation", back_populates="user")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="refresh_tokens")


class Installation(Base):
    __tablename__ = "installations"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    app_version = Column(String(50))
    platform = Column(String(50))
    first_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user = relationship("User", back_populates="installations")
    daily_activities = relationship("DailyInstallationActivity", back_populates="installation", cascade="all, delete-orphan")


class DailyInstallationActivity(Base):
    __tablename__ = "daily_installation_activity"

    date = Column(Date, primary_key=True)
    installation_id = Column(UUID(as_uuid=True), ForeignKey("installations.id", ondelete="CASCADE"), primary_key=True)

    installation = relationship("Installation", back_populates="daily_activities")


class DailyUsage(Base):
    __tablename__ = "daily_usage"

    date = Column(Date, primary_key=True)
    active_installations = Column(Integer, default=0)
    new_installations = Column(Integer, default=0)
    active_accounts = Column(Integer, default=0)
