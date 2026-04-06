"""Session management routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import secrets

from aigernon.api.deps import get_current_user, get_db
from aigernon.api.db.database import Database

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    """Create session request."""
    name: str
    context: Optional[str] = None
    project_id: Optional[str] = None


class SessionResponse(BaseModel):
    """Session response."""
    id: str
    name: str
    context: Optional[str]
    project_id: Optional[str]
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    """Session list response."""
    sessions: list[SessionResponse]


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """List user's sessions."""
    sessions = await db.list_sessions(user["id"])
    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s["id"],
                name=s["name"],
                context=s.get("context"),
                project_id=s.get("project_id"),
                created_at=s["created_at"],
                updated_at=s["updated_at"],
            )
            for s in sessions
        ]
    )


@router.post("", response_model=SessionResponse)
async def create_session(
    request: SessionCreate,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Create a new session."""
    session_id = f"sess_{secrets.token_urlsafe(8)}"

    session = await db.create_session(
        session_id=session_id,
        user_id=user["id"],
        name=request.name,
        context=request.context,
        project_id=request.project_id,
    )

    return SessionResponse(
        id=session["id"],
        name=session["name"],
        context=session.get("context"),
        project_id=session.get("project_id"),
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Get a session by ID."""
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session["id"],
        name=session["name"],
        context=session.get("context"),
        project_id=session.get("project_id"),
        created_at=session["created_at"],
        updated_at=session["updated_at"],
    )


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    """Delete a session."""
    session = await db.get_session(session_id)
    if not session or session["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete_session(session_id)
    return {"message": "Session deleted"}
