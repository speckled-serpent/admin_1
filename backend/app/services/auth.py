"""Local username/password login and bearer sessions stored in SQLite."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import InvalidCredentials
from app.models import AuthSession, User
from app.security import hash_password, hash_token, new_token, verify_password

# Used when the username does not exist so the hash work stays similar.
_DUMMY_PASSWORD_HASH = hash_password("not-a-real-password")


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def register_user(db: Session, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, username: str, password: str, *, ttl_hours: int) -> tuple[str, datetime, User]:
    user = db.scalar(select(User).where(User.username == username))
    stored = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    if user is None or not verify_password(password, stored):
        raise InvalidCredentials()
    token = new_token()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)
    db.add(AuthSession(token_hash=hash_token(token), user_id=user.id, expires_at=expires_at))
    db.commit()
    return token, expires_at, user


def user_for_token(db: Session, token: str) -> User | None:
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if row is None:
        return None
    if as_utc(row.expires_at) <= datetime.now(timezone.utc):
        db.delete(row)
        db.commit()
        return None
    return row.user


def logout(db: Session, token: str) -> None:
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if row is not None:
        db.delete(row)
        db.commit()
