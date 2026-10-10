"""API request and response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class LoginOut(BaseModel):
    token: str
    token_type: str = "bearer"
    expires_at: datetime
    username: str


class UserOut(BaseModel):
    username: str


class ProjectOut(BaseModel):
    slug: str
    name: str


class ProjectDetail(BaseModel):
    slug: str
    name: str
    panels: list[str]


class ConnectionDraftIn(BaseModel):
    key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    kind: str
    url: str | None = None
    expected_status: int | None = None
    timeout_seconds: int | None = None
    secret: str | None = None


class SourceDraftIn(BaseModel):
    panel: str
    mode: str
    connection: str | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    panels: list[str] = Field(min_length=1)
    connections: list[ConnectionDraftIn] | None = None
    sources: list[SourceDraftIn] | None = None


class PanelOut(BaseModel):
    key: str
    label: str
    group: str
    description: str


class ChargeOut(BaseModel):
    id: str
    amount: int
    amount_refunded: int
    currency: str
    status: str
    refunded: bool
    created: int
    description: str | None = None
    customer: str | None = None


class ApiKeyOut(BaseModel):
    prefix: str
    created_at: datetime


class ConnectionIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str
    url: str | None = None
    expected_status: int | None = None
    timeout_seconds: int | None = None
    secret: str | None = None


class ConnectionOut(BaseModel):
    id: int
    name: str
    kind: str
    url: str | None
    expected_status: int | None
    timeout_seconds: int | None
    has_secret: bool
    api_key: ApiKeyOut | None
    last_received_at: datetime | None
    last_status: str | None


class PanelSettingsOut(BaseModel):
    panel_key: str
    mode: str
    connection_id: int | None
    allowed_modes: list[str]
    last_received_at: datetime | None
    last_status: str | None
    connections: list[ConnectionOut]


class PanelSettingsUpdate(BaseModel):
    mode: str
    connection_id: int | None = None
    new_connection: ConnectionIn | None = None


class IssuedApiKeyOut(BaseModel):
    key: str
    prefix: str
    created_at: datetime


class IngestOut(BaseModel):
    accepted: list[str]


class ConnectionTestOut(BaseModel):
    ok: bool
    detail: str
    last_received_at: datetime | None
    last_status: str | None


class RevenueOut(BaseModel):
    project: ProjectOut
    currency: str | None
    gross_amount: int
    refunded_amount: int
    net_amount: int
    charge_count: int
    succeeded_count: int
    refunded_count: int
    charges: list[ChargeOut]
