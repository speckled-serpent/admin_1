"""Login, logout, and the current local user."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.deps import get_current_user
from app.errors import InvalidCredentials
from app.models import User
from app.schemas import LoginIn, LoginOut, UserOut
from app.services.auth import login, logout

router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer(auto_error=False)


@router.post("/login", response_model=LoginOut)
def login_route(
    body: LoginIn,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginOut:
    try:
        token, expires_at, user = login(
            db,
            body.username,
            body.password,
            ttl_hours=settings.session_ttl_hours,
        )
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="Invalid username or password") from None
    return LoginOut(token=token, expires_at=expires_at, username=user.username)


@router.post("/logout", status_code=204)
def logout_route(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
    _user: Annotated[User, Depends(get_current_user)],
) -> Response:
    if credentials is not None:
        logout(db, credentials.credentials)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
def me_route(user: Annotated[User, Depends(get_current_user)]) -> UserOut:
    return UserOut(username=user.username)
