"""Memory routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime, timedelta

from aigernon.api.deps import get_current_user, get_workspace

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryEntry(BaseModel):
    """Memory entry."""
    date: str
    content: str


class TodayMemoryResponse(BaseModel):
    """Today's memory response."""
    date: str
    content: str
    has_content: bool


class LongTermMemoryResponse(BaseModel):
    """Long-term memory response."""
    content: str


class SearchResult(BaseModel):
    """Search result."""
    text: str
    score: float
    source: Optional[str]
    title: Optional[str]


class SearchResponse(BaseModel):
    """Search response."""
    results: list[SearchResult]
    query: str


@router.get("/today", response_model=TodayMemoryResponse)
async def get_today_memory(
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get today's memory."""
    today = datetime.now().strftime("%Y-%m-%d")
    memory_file = workspace / "memory" / f"{today}.md"

    if memory_file.exists():
        content = memory_file.read_text()
        return TodayMemoryResponse(
            date=today,
            content=content,
            has_content=bool(content.strip()),
        )

    return TodayMemoryResponse(
        date=today,
        content="",
        has_content=False,
    )


@router.get("/recent")
async def get_recent_memory(
    days: int = 7,
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
) -> list[MemoryEntry]:
    """Get recent memory entries."""
    memory_dir = workspace / "memory"
    entries = []

    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        memory_file = memory_dir / f"{date}.md"

        if memory_file.exists():
            content = memory_file.read_text()
            if content.strip():
                entries.append(MemoryEntry(date=date, content=content))

    return entries


@router.get("/long-term", response_model=LongTermMemoryResponse)
async def get_long_term_memory(
    user: dict = Depends(get_current_user),
    workspace: Path = Depends(get_workspace),
):
    """Get long-term memory."""
    memory_file = workspace / "memory" / "MEMORY.md"

    if memory_file.exists():
        content = memory_file.read_text()
        return LongTermMemoryResponse(content=content)

    return LongTermMemoryResponse(content="")


@router.get("/search", response_model=SearchResponse)
async def search_memory(
    q: str,
    collection: str = "memories",
    limit: int = 5,
    user: dict = Depends(get_current_user),
):
    """Search vector memory."""
    try:
        from aigernon.config.loader import load_config, get_data_dir
        from aigernon.memory.vector import create_vector_store

        config = load_config()
        data_dir = get_data_dir()

        store = create_vector_store(
            data_dir=data_dir,
            api_key=config.get_api_key(),
            api_base=config.get_api_base(),
            embedding_model=config.vector.embedding_model,
        )

        results = store.search(collection, q, n_results=limit)

        return SearchResponse(
            query=q,
            results=[
                SearchResult(
                    text=r.text,
                    score=r.score,
                    source=r.metadata.get("source"),
                    title=r.metadata.get("title"),
                )
                for r in results
            ],
        )
    except ImportError:
        raise HTTPException(
            status_code=501, detail="Vector memory not available (install chromadb)"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
