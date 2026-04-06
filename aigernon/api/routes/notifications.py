"""Notifications routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from aigernon.api.deps import get_current_user, get_db
from aigernon.api.db.database import Database

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    """Notification response."""
    id: str
    type: str
    title: str
    body: Optional[str]
    urgency: str
    action_url: Optional[str]
    created_at: str
    read_at: Optional[str]


class NotificationListResponse(BaseModel):
    """Notification list response."""
    notifications: list[NotificationResponse]
    unread_count: int


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = 50,
    unread_only: bool = False,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """List user's notifications."""
    notifications = await db.list_notifications(
        user["id"], limit=limit, unread_only=unread_only
    )
    unread_count = await db.count_unread_notifications(user["id"])

    return NotificationListResponse(
        notifications=[
            NotificationResponse(
                id=n["id"],
                type=n["type"],
                title=n["title"],
                body=n.get("body"),
                urgency=n.get("urgency", "low"),
                action_url=n.get("action_url"),
                created_at=n["created_at"],
                read_at=n.get("read_at"),
            )
            for n in notifications
        ],
        unread_count=unread_count,
    )


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Mark a notification as read."""
    await db.mark_notification_read(notification_id)
    return {"message": "Notification marked as read"}


@router.post("/read-all")
async def mark_all_read(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Mark all notifications as read."""
    count = await db.mark_all_notifications_read(user["id"])
    return {"message": f"Marked {count} notifications as read"}


@router.get("/count")
async def get_unread_count(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Get unread notification count."""
    count = await db.count_unread_notifications(user["id"])
    return {"unread_count": count}
