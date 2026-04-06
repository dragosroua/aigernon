"""Coaching routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from aigernon.api.deps import get_current_user, get_workspace
from aigernon.coaching.store import CoachingStore

router = APIRouter(prefix="/coaching", tags=["coaching"])


class ClientResponse(BaseModel):
    """Client response."""
    client_id: str
    name: str
    coach_chat_id: str
    coach_channel: str
    timezone: str
    created_at: Optional[str]


class ClientListResponse(BaseModel):
    """Client list response."""
    clients: list[ClientResponse]


class CreateClientRequest(BaseModel):
    """Create client request."""
    client_id: str
    name: str
    coach_chat_id: str
    coach_channel: str = "web"
    timezone: str = "UTC"


class AddIdeaRequest(BaseModel):
    """Add idea request."""
    content: str
    realm: str = "assess"


class AddQuestionRequest(BaseModel):
    """Add question request."""
    content: str


class ContentResponse(BaseModel):
    """Content response."""
    content: str


class PrepSummaryResponse(BaseModel):
    """Prep summary response."""
    client_name: str
    last_session: Optional[str]
    ideas: str
    questions: str
    flags: str
    flag_count: int
    history: str


class SessionsResponse(BaseModel):
    """Sessions list response."""
    sessions: list[str]


@router.get("/clients", response_model=ClientListResponse)
async def list_clients(
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """List all coaching clients."""
    store = CoachingStore(workspace)
    clients = store.list_clients()
    return ClientListResponse(
        clients=[ClientResponse(**c) for c in clients]
    )


@router.post("/clients", response_model=ClientResponse)
async def create_client(
    request: CreateClientRequest,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Create a new coaching client."""
    store = CoachingStore(workspace)

    # Check if client already exists
    existing = store.get_client(request.client_id)
    if existing:
        raise HTTPException(status_code=400, detail="Client already exists")

    client = store.add_client(
        client_id=request.client_id,
        name=request.name,
        coach_chat_id=request.coach_chat_id,
        coach_channel=request.coach_channel,
        timezone=request.timezone,
    )
    return ClientResponse(**client)


@router.get("/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: str,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get a specific client."""
    store = CoachingStore(workspace)
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return ClientResponse(**client)


@router.get("/clients/{client_id}/prep", response_model=PrepSummaryResponse)
async def get_prep_summary(
    client_id: str,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get pre-session prep summary for a client."""
    store = CoachingStore(workspace)
    prep = store.get_prep_summary(client_id)

    if "error" in prep:
        raise HTTPException(status_code=404, detail=prep["error"])

    return PrepSummaryResponse(
        client_name=prep["client"]["name"],
        last_session=prep["last_session"],
        ideas=prep["ideas"],
        questions=prep["questions"],
        flags=prep["flags"],
        flag_count=prep["flag_count"],
        history=prep["history"],
    )


@router.post("/clients/{client_id}/ideas")
async def add_idea(
    client_id: str,
    request: AddIdeaRequest,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Add an idea for a client."""
    store = CoachingStore(workspace)
    store.add_idea(client_id, request.content, request.realm)
    return {"success": True}


@router.get("/clients/{client_id}/ideas", response_model=ContentResponse)
async def get_ideas(
    client_id: str,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get ideas for a client."""
    store = CoachingStore(workspace)
    ideas = store.get_ideas(client_id)
    return ContentResponse(content=ideas)


@router.post("/clients/{client_id}/questions")
async def add_question(
    client_id: str,
    request: AddQuestionRequest,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Add a question for a client."""
    store = CoachingStore(workspace)
    store.add_question(client_id, request.content)
    return {"success": True}


@router.get("/clients/{client_id}/questions", response_model=ContentResponse)
async def get_questions(
    client_id: str,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get questions for a client."""
    store = CoachingStore(workspace)
    questions = store.get_questions(client_id)
    return ContentResponse(content=questions)


@router.get("/clients/{client_id}/sessions", response_model=SessionsResponse)
async def list_sessions(
    client_id: str,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """List all session dates for a client."""
    store = CoachingStore(workspace)
    sessions = store.list_sessions(client_id)
    return SessionsResponse(sessions=sessions)


@router.get("/clients/{client_id}/sessions/{date}", response_model=ContentResponse)
async def get_session(
    client_id: str,
    date: str,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get session notes for a specific date."""
    store = CoachingStore(workspace)
    content = store.get_session(client_id, date)
    if content is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return ContentResponse(content=content)


class AddSessionRequest(BaseModel):
    """Add session request."""
    date: str
    content: str


@router.post("/clients/{client_id}/sessions")
async def add_session(
    client_id: str,
    request: AddSessionRequest,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Add session notes for a client."""
    store = CoachingStore(workspace)
    store.add_session(client_id, request.date, request.content)
    return {"success": True}


class UpdateHistoryRequest(BaseModel):
    """Update history request."""
    content: str


@router.get("/clients/{client_id}/history", response_model=ContentResponse)
async def get_history(
    client_id: str,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get coaching arc/history for a client."""
    store = CoachingStore(workspace)
    history = store.get_history(client_id)
    return ContentResponse(content=history)


@router.put("/clients/{client_id}/history")
async def update_history(
    client_id: str,
    request: UpdateHistoryRequest,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Update coaching arc/history for a client."""
    store = CoachingStore(workspace)
    store.update_history(client_id, request.content)
    return {"success": True}


class AddFlagRequest(BaseModel):
    """Add flag request."""
    message: str
    grounding_offered: bool = False
    coach_notified: bool = False


@router.post("/clients/{client_id}/flags")
async def add_flag(
    client_id: str,
    request: AddFlagRequest,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Add an emergency flag for a client."""
    store = CoachingStore(workspace)
    store.add_flag(client_id, request.message, request.grounding_offered, request.coach_notified)
    return {"success": True}


@router.get("/clients/{client_id}/flags", response_model=ContentResponse)
async def get_flags(
    client_id: str,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get emergency flags for a client."""
    store = CoachingStore(workspace)
    flags = store.get_flags(client_id)
    return ContentResponse(content=flags)
