"""Push ingest. Authenticated with a connection API key, never a user session."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.errors import InvalidCredentials, InvalidPayload
from app.schemas import IngestOut
from app.services.connections import accept_ingest, connection_for_ingest_key

router = APIRouter(tags=["ingest"])
_bearer = HTTPBearer(auto_error=False)


@router.post("/ingest/{slug}", response_model=IngestOut)
def ingest_route(
    slug: str,
    body: dict,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> IngestOut:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid API key", headers={"WWW-Authenticate": "Bearer"})
    try:
        project, connection = connection_for_ingest_key(db, slug, credentials.credentials)
    except InvalidCredentials:
        raise HTTPException(status_code=401, detail="Invalid API key", headers={"WWW-Authenticate": "Bearer"}) from None
    try:
        accepted = accept_ingest(db, project, connection, body)
    except InvalidPayload as exc:
        raise HTTPException(status_code=422, detail=exc.detail) from None
    return IngestOut(accepted=accepted)
