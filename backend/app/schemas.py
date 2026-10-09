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


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    panels: list[str] = Field(min_length=1)


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
