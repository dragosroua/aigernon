"""Projects routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from aigernon.api.deps import get_current_user, get_project_store
from aigernon.projects.store import ProjectStore

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectResponse(BaseModel):
    """Project response."""
    id: str
    name: str
    realm: str
    repo: Optional[str]
    current_version: Optional[str]


class ProjectListResponse(BaseModel):
    """Project list response."""
    projects: list[ProjectResponse]


class TaskResponse(BaseModel):
    """Task response."""
    id: str
    title: str
    description: Optional[str]
    type: str
    status: str
    version: Optional[str]
    branch: Optional[str]


class TaskListResponse(BaseModel):
    """Task list response."""
    tasks: list[TaskResponse]


class ProjectDetailResponse(BaseModel):
    """Project detail response."""
    id: str
    name: str
    realm: str
    repo: Optional[str]
    current_version: Optional[str]
    realm_time: str
    tasks: list[TaskResponse]


class IdeaResponse(BaseModel):
    """Idea response."""
    id: str
    title: str
    items: list[str]


class IdeaListResponse(BaseModel):
    """Idea list response."""
    ideas: list[IdeaResponse]


class CreateProjectRequest(BaseModel):
    """Create project request."""
    name: str
    realm: str = "assess"
    repo: Optional[str] = None


@router.post("", response_model=ProjectResponse)
async def create_project(
    request: CreateProjectRequest,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Create a new project."""
    # add_project returns project_id, then we get the full project
    project_id = store.add_project(
        name=request.name,
        repo=request.repo or "",
    )
    project = store.get_project(project_id)

    # If a specific realm was requested (not default assess), move to it
    if request.realm and request.realm != "assess":
        # For new projects, we can set realm directly since there are no tasks yet
        store._update_project(project_id, realm=request.realm)
        project = store.get_project(project_id)

    return ProjectResponse(
        id=project.get("id", project_id),
        name=project.get("name", request.name),
        realm=project.get("realm", "assess"),
        repo=project.get("repo"),
        current_version=project.get("current_version"),
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    realm: Optional[str] = None,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """List all projects."""
    projects = store.list_projects(realm=realm)
    return ProjectListResponse(
        projects=[
            ProjectResponse(
                id=p.get("id", ""),
                name=p.get("name", ""),
                realm=p.get("realm", "assess"),
                repo=p.get("repo"),
                current_version=p.get("current_version"),
            )
            for p in projects
        ]
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse)
async def get_project(
    project_id: str,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Get project details."""
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = store.list_tasks(project_id)

    return ProjectDetailResponse(
        id=project.get("id", project_id),
        name=project.get("name", ""),
        realm=project.get("realm", "assess"),
        repo=project.get("repo"),
        current_version=project.get("current_version"),
        realm_time=store.format_realm_time(project_id),
        tasks=[
            TaskResponse(
                id=t["id"],
                title=t["title"],
                description=t.get("description"),
                type=t.get("type", "feature"),
                status=t.get("status", "draft"),
                version=t.get("version"),
                branch=t.get("branch"),
            )
            for t in tasks
        ],
    )


@router.get("/{project_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    project_id: str,
    status: Optional[str] = None,
    version: Optional[str] = None,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """List tasks for a project."""
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks = store.list_tasks(project_id, status=status, version=version)

    return TaskListResponse(
        tasks=[
            TaskResponse(
                id=t["id"],
                title=t["title"],
                description=t.get("description"),
                type=t.get("type", "feature"),
                status=t.get("status", "draft"),
                version=t.get("version"),
                branch=t.get("branch"),
            )
            for t in tasks
        ]
    )


@router.get("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    project_id: str,
    task_id: str,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Get task details."""
    task = store.get_task(project_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return TaskResponse(
        id=task["id"],
        title=task["title"],
        description=task.get("description"),
        type=task.get("type", "feature"),
        status=task.get("status", "draft"),
        version=task.get("version"),
        branch=task.get("branch"),
    )


class CreateTaskRequest(BaseModel):
    """Create task request."""
    title: str
    description: str = ""
    type: str = "feature"


@router.post("/{project_id}/tasks", response_model=TaskResponse)
async def create_task(
    project_id: str,
    request: CreateTaskRequest,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Create a new task for a project."""
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.get("realm") != "assess":
        raise HTTPException(status_code=400, detail="Tasks can only be added in Assess realm")

    task_id = store.add_task(
        project_id=project_id,
        title=request.title,
        description=request.description,
        task_type=request.type,
    )

    if not task_id:
        raise HTTPException(status_code=400, detail="Failed to create task")

    task = store.get_task(project_id, task_id)
    return TaskResponse(
        id=task["id"],
        title=task["title"],
        description=task.get("description"),
        type=task.get("type", "feature"),
        status=task.get("status", "draft"),
        version=task.get("version"),
        branch=task.get("branch"),
    )


class UpdateTaskRequest(BaseModel):
    """Update task request."""
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None


@router.put("/{project_id}/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    project_id: str,
    task_id: str,
    request: UpdateTaskRequest,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Update a task."""
    task = store.get_task(project_id, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    updates = {}
    if request.title is not None:
        updates["title"] = request.title
    if request.description is not None:
        updates["description"] = request.description
    if request.type is not None:
        updates["type"] = request.type

    if updates:
        store.update_task(project_id, task_id, **updates)

    task = store.get_task(project_id, task_id)
    return TaskResponse(
        id=task["id"],
        title=task["title"],
        description=task.get("description"),
        type=task.get("type", "feature"),
        status=task.get("status", "draft"),
        version=task.get("version"),
        branch=task.get("branch"),
    )


@router.delete("/{project_id}/tasks/{task_id}")
async def delete_task(
    project_id: str,
    task_id: str,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Delete a task."""
    if not store.delete_task(project_id, task_id):
        raise HTTPException(status_code=400, detail="Cannot delete task (not in Assess realm or not found)")
    return {"success": True}


@router.post("/{project_id}/tasks/{task_id}/ready")
async def mark_task_ready(
    project_id: str,
    task_id: str,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Mark a task as ready (done defining)."""
    if not store.mark_task_ready(project_id, task_id):
        raise HTTPException(status_code=400, detail="Cannot mark task ready (must be in Assess realm with draft status)")
    return {"success": True}


class ScheduleTaskRequest(BaseModel):
    """Schedule task request."""
    version: str


@router.post("/{project_id}/tasks/{task_id}/schedule")
async def schedule_task(
    project_id: str,
    task_id: str,
    request: ScheduleTaskRequest,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Schedule a task to a version."""
    if not store.schedule_task(project_id, task_id, request.version):
        raise HTTPException(status_code=400, detail="Cannot schedule task (must be in Decide realm with unscheduled status)")
    return {"success": True}


class StartTaskRequest(BaseModel):
    """Start task request."""
    branch: Optional[str] = None


@router.post("/{project_id}/tasks/{task_id}/start")
async def start_task(
    project_id: str,
    task_id: str,
    request: StartTaskRequest,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Start working on a task."""
    if not store.start_task(project_id, task_id, request.branch):
        raise HTTPException(status_code=400, detail="Cannot start task (must be in Do realm with scheduled status)")
    return {"success": True}


class CompleteTaskRequest(BaseModel):
    """Complete task request."""
    execution_log: str = ""


@router.post("/{project_id}/tasks/{task_id}/complete")
async def complete_task(
    project_id: str,
    task_id: str,
    request: CompleteTaskRequest,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Mark a task as complete."""
    if not store.complete_task(project_id, task_id, request.execution_log):
        raise HTTPException(status_code=400, detail="Cannot complete task (must be in Do realm with in_progress or blocked status)")
    return {"success": True}


class BlockTaskRequest(BaseModel):
    """Block task request."""
    reason: str


@router.post("/{project_id}/tasks/{task_id}/block")
async def block_task(
    project_id: str,
    task_id: str,
    request: BlockTaskRequest,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Mark a task as blocked."""
    if not store.block_task(project_id, task_id, request.reason):
        raise HTTPException(status_code=400, detail="Cannot block task")
    return {"success": True}


@router.post("/{project_id}/tasks/{task_id}/unblock")
async def unblock_task(
    project_id: str,
    task_id: str,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Unblock a task."""
    if not store.unblock_task(project_id, task_id):
        raise HTTPException(status_code=400, detail="Cannot unblock task")
    return {"success": True}


class MoveProjectRequest(BaseModel):
    """Move project request."""
    target_realm: str
    reason: Optional[str] = None


@router.post("/{project_id}/move")
async def move_project(
    project_id: str,
    request: MoveProjectRequest,
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """Move project to different realm."""
    success, issues = store.move_project_to_realm(
        project_id, request.target_realm, request.reason
    )

    if not success:
        raise HTTPException(status_code=400, detail={"issues": issues})

    return {"realm": request.target_realm}


@router.get("/ideas", response_model=IdeaListResponse)
async def list_ideas(
    user: dict = Depends(get_current_user),
    store: ProjectStore = Depends(get_project_store),
):
    """List all ideas."""
    ideas = store.list_ideas()
    return IdeaListResponse(
        ideas=[
            IdeaResponse(
                id=i["id"],
                title=i["title"],
                items=i.get("items", []),
            )
            for i in ideas
        ]
    )
