import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db
from app.models.notification import Notification
from app.models.schemas import NotificationCreate, NotificationListResponse, NotificationResponse
from app.services.publisher import publish_notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post(
    "",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_notification(
    payload: NotificationCreate,
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    notification = Notification(
        recipient_email=payload.recipient_email,
        subject=payload.subject,
        body=payload.body,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    await publish_notification(
        notification_id=notification.id,
        recipient_email=notification.recipient_email,
        subject=notification.subject,
        body=notification.body,
    )
    return NotificationResponse.model_validate(notification)


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification {notification_id} not found",
        )
    return NotificationResponse.model_validate(notification)


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> NotificationListResponse:
    query = select(Notification)
    count_query = select(func.count()).select_from(Notification)

    if status_filter:
        query = query.where(Notification.status == status_filter)
        count_query = count_query.where(Notification.status == status_filter)

    query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)

    results = await db.execute(query)
    total_result = await db.execute(count_query)

    notifications = results.scalars().all()
    total = total_result.scalar_one()

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
    )
