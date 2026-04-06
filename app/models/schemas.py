import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.notification import NotificationStatus


class NotificationCreate(BaseModel):
    recipient_email: EmailStr
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)

    @field_validator("subject")
    @classmethod
    def subject_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("subject must not be blank")
        return v


class NotificationResponse(BaseModel):
    id: uuid.UUID
    recipient_email: str
    subject: str
    body: str
    status: NotificationStatus
    retry_count: int
    created_at: datetime
    updated_at: datetime
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class NotificationListResponse(BaseModel):
    items: list[NotificationResponse]
    total: int


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    version: str = "1.0.0"
