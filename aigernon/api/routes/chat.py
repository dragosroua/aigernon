"""Chat routes."""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from aigernon.api.deps import (
    get_current_user,
    get_current_user_ws,
    get_agent_loop,
    get_ws_manager,
    get_db,
)
from aigernon.api.websocket import WebSocketManager
from aigernon.api.db.database import Database
from aigernon.agent.loop import AgentLoop

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat message request."""
    message: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    """Chat response."""
    content: str
    realm: Optional[str] = None
    timestamp: str


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    user: dict = Depends(get_current_user),
    agent: AgentLoop = Depends(get_agent_loop),
    db: Database = Depends(get_db),
):
    """Send a message and get a response (non-streaming)."""
    session_key = f"web:{user['id']}:{request.session_id}"

    # Update session timestamp
    session = await db.get_session(request.session_id)
    if session:
        await db.update_session(request.session_id)

    # Process through agent
    response = await agent.process_direct(
        request.message,
        session_key=session_key,
        channel="web",
        chat_id=user["id"],
    )

    # Extract realm from response metadata if available
    realm = None  # TODO: Extract from agent context

    return ChatResponse(
        content=response or "",
        realm=realm,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ws_manager: WebSocketManager = Depends(get_ws_manager),
    db: Database = Depends(get_db),
):
    """WebSocket endpoint for real-time chat."""
    from loguru import logger

    # Authenticate from cookie or query param (before accepting)
    user = await get_current_user_ws(websocket)
    if not user:
        logger.debug("WebSocket auth failed - no user")
        await websocket.accept()  # Must accept before close
        await websocket.close(code=4001)
        return

    logger.debug(f"WebSocket authenticated for user: {user['id']}")

    # Get session from query params
    session_id = websocket.query_params.get("session_id", "default")

    # Connect
    connection = await ws_manager.connections.connect(
        websocket, user["id"], session_id
    )

    # Try to get agent loop (may not be initialized)
    from aigernon.api import deps
    agent = deps._agent_loop

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            if data.get("type") == "message":
                message = data.get("content", "")
                if not message:
                    continue

                session_key = f"web:{user['id']}:{session_id}"

                # Send typing indicator
                await ws_manager.send_typing_indicator(user["id"], session_id, True)

                # Process message
                try:
                    if agent:
                        response = await agent.process_direct(
                            message,
                            session_key=session_key,
                            channel="web",
                            chat_id=user["id"],
                        )
                    else:
                        # No agent available - send error
                        response = "Agent not initialized. Please start AIGernon with the API server."
                        logger.warning("Agent loop not available for WebSocket chat")

                    # Send response
                    await ws_manager.send_chat_message(
                        user_id=user["id"],
                        session_id=session_id,
                        content=response or "",
                        is_complete=True,
                    )
                finally:
                    # Clear typing indicator
                    await ws_manager.send_typing_indicator(user["id"], session_id, False)

            elif data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.connections.disconnect(connection)


class RealmFlowResponse(BaseModel):
    """Realm flow response."""
    current_realm: Optional[str]
    today: dict
    history: list


@router.get("/realm", response_model=RealmFlowResponse)
async def get_realm_flow(
    user: dict = Depends(get_current_user),
):
    """Get realm flow statistics for today."""
    # TODO: Implement realm tracking from agent context
    return RealmFlowResponse(
        current_realm="assess",
        today={
            "assess": 0.6,
            "decide": 0.25,
            "do": 0.15,
        },
        history=[],
    )
