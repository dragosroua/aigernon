"""Project store for iOS app development with ADD workflow."""

from pathlib import Path
from datetime import datetime
from typing import Optional
import re
import yaml

from aigernon.utils.helpers import ensure_dir, safe_filename


class ProjectStore:
    """
    Data store for projects module.

    Manages iOS app projects through Assess -> Decide -> Do workflow.
    Includes ideas (brainstorming), projects, tasks, and versions.
    """

    REALMS = ("assess", "decide", "do")
    TASK_STATUSES = ("draft", "ready", "unscheduled", "scheduled", "in_progress", "blocked", "done")
    TASK_TYPES = ("feature", "bug")
    VERSION_STATUSES = ("planned", "active", "ready", "released")

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.projects_dir = ensure_dir(workspace / "projects")
        self.ideas_dir = ensure_dir(workspace / "ideas")

    # -------------------------------------------------------------------------
    # Path Helpers
    # -------------------------------------------------------------------------

    def _project_dir(self, project_id: str) -> Path:
        """Get the directory for a specific project."""
        safe_id = safe_filename(project_id)
        return self.projects_dir / safe_id

    def _ensure_project_dir(self, project_id: str) -> Path:
        """Ensure project directory exists with required subdirectories."""
        project_dir = ensure_dir(self._project_dir(project_id))
        ensure_dir(project_dir / "tasks")
        ensure_dir(project_dir / "versions")
        return project_dir

    def _idea_path(self, idea_id: str) -> Path:
        """Get the path for a specific idea."""
        safe_id = safe_filename(idea_id)
        return self.ideas_dir / f"{safe_id}.md"

    def _task_path(self, project_id: str, task_id: str) -> Path:
        """Get the path for a specific task."""
        return self._project_dir(project_id) / "tasks" / f"{task_id}.yaml"

    def _version_path(self, project_id: str, version: str) -> Path:
        """Get the path for a specific version."""
        safe_version = version.replace(".", "_")
        return self._project_dir(project_id) / "versions" / f"{safe_version}.yaml"

    def _generate_task_id(self, project_id: str) -> str:
        """Generate the next task ID for a project."""
        tasks_dir = self._project_dir(project_id) / "tasks"
        if not tasks_dir.exists():
            return "001"

        existing = list(tasks_dir.glob("*.yaml"))
        if not existing:
            return "001"

        # Find highest number
        max_num = 0
        for task_file in existing:
            try:
                num = int(task_file.stem)
                max_num = max(max_num, num)
            except ValueError:
                continue

        return f"{max_num + 1:03d}"

    # -------------------------------------------------------------------------
    # Ideas
    # -------------------------------------------------------------------------

    def add_idea(self, title: str) -> str:
        """
        Add a new idea.

        Args:
            title: Idea title

        Returns:
            idea_id (slugified title)
        """
        idea_id = safe_filename(title.lower().replace(" ", "-"))
        idea_path = self._idea_path(idea_id)

        content = f"# {title}\n\n"
        idea_path.write_text(content)

        return idea_id

    def get_idea(self, idea_id: str) -> Optional[dict]:
        """
        Get an idea by ID.

        Returns:
            dict with 'id', 'title', 'items', or None if not found
        """
        idea_path = self._idea_path(idea_id)
        if not idea_path.exists():
            return None

        content = idea_path.read_text()
        lines = content.strip().split("\n")

        # Extract title from first line
        title = lines[0].lstrip("# ").strip() if lines else idea_id

        # Extract items (lines starting with -)
        items = []
        for line in lines[1:]:
            line = line.strip()
            if line.startswith("- "):
                items.append(line[2:])

        return {
            "id": idea_id,
            "title": title,
            "items": items,
        }

    def list_ideas(self) -> list[dict]:
        """List all ideas."""
        ideas = []

        if not self.ideas_dir.exists():
            return ideas

        for idea_file in sorted(self.ideas_dir.glob("*.md")):
            idea = self.get_idea(idea_file.stem)
            if idea:
                ideas.append(idea)

        return ideas

    def add_idea_item(self, idea_id: str, item: str) -> bool:
        """
        Add an item to an idea.

        Returns:
            True if successful, False if idea not found
        """
        idea_path = self._idea_path(idea_id)
        if not idea_path.exists():
            return False

        content = idea_path.read_text()
        # Ensure newline before adding item
        if not content.endswith("\n"):
            content += "\n"
        content += f"- {item}\n"
        idea_path.write_text(content)

        return True

    def remove_idea_item(self, idea_id: str, item_index: int) -> bool:
        """
        Remove an item from an idea by index.

        Returns:
            True if successful, False if idea not found or index invalid
        """
        idea = self.get_idea(idea_id)
        if not idea:
            return False

        if item_index < 0 or item_index >= len(idea["items"]):
            return False

        # Rebuild content without the item
        idea_path = self._idea_path(idea_id)
        content = idea_path.read_text()
        lines = content.split("\n")

        # Find and remove the item line
        item_count = 0
        new_lines = []
        for line in lines:
            if line.strip().startswith("- "):
                if item_count == item_index:
                    item_count += 1
                    continue  # Skip this line
                item_count += 1
            new_lines.append(line)

        idea_path.write_text("\n".join(new_lines))
        return True

    def delete_idea(self, idea_id: str) -> bool:
        """
        Delete an idea.

        Returns:
            True if deleted, False if not found
        """
        idea_path = self._idea_path(idea_id)
        if not idea_path.exists():
            return False

        idea_path.unlink()
        return True

    def convert_idea_to_project(self, idea_id: str, repo: str) -> Optional[str]:
        """
        Convert an idea to a project.

        Creates project with idea title as name, items as draft tasks.
        Deletes the idea after conversion.

        Args:
            idea_id: Idea to convert
            repo: Git repository URL

        Returns:
            project_id if successful, None if idea not found
        """
        idea = self.get_idea(idea_id)
        if not idea:
            return None

        # Create project
        project_id = self.add_project(idea["title"], repo)

        # Create tasks from items
        for item in idea["items"]:
            self.add_task(
                project_id=project_id,
                title=item,
                description="",
                task_type="feature",
            )

        # Delete the idea
        self.delete_idea(idea_id)

        return project_id

    # -------------------------------------------------------------------------
    # Projects
    # -------------------------------------------------------------------------

    def add_project(self, name: str, repo: str) -> str:
        """
        Add a new project.

        Args:
            name: Project name
            repo: Git repository URL

        Returns:
            project_id (slugified name)
        """
        project_id = safe_filename(name.lower().replace(" ", "-"))
        project_dir = self._ensure_project_dir(project_id)

        config = {
            "name": name,
            "repo": repo,
            "realm": "assess",
            "current_version": None,
            "created_at": datetime.now().isoformat(),
        }

        config_path = project_dir / "project.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))

        # Initialize transitions log
        transitions_path = project_dir / "transitions.log"
        timestamp = datetime.now().isoformat()
        transitions_path.write_text(f"{timestamp} | created | assess\n")

        return project_id

    def get_project(self, project_id: str) -> Optional[dict]:
        """Get project configuration."""
        project_dir = self._project_dir(project_id)
        config_path = project_dir / "project.yaml"

        if not config_path.exists():
            return None

        config = yaml.safe_load(config_path.read_text())
        config["id"] = project_id
        return config

    def list_projects(self, realm: Optional[str] = None) -> list[dict]:
        """
        List all projects, optionally filtered by realm.

        Args:
            realm: Filter by realm (assess, decide, do)

        Returns:
            List of project configs
        """
        projects = []

        if not self.projects_dir.exists():
            return projects

        for project_dir in sorted(self.projects_dir.iterdir()):
            if project_dir.is_dir():
                config_path = project_dir / "project.yaml"
                if config_path.exists():
                    config = yaml.safe_load(config_path.read_text())
                    config["id"] = project_dir.name

                    if realm is None or config.get("realm") == realm:
                        projects.append(config)

        return projects

    def _update_project(self, project_id: str, **fields) -> bool:
        """Update project fields."""
        project = self.get_project(project_id)
        if not project:
            return False

        project.update(fields)
        # Remove 'id' before saving (it's derived from directory)
        project.pop("id", None)

        config_path = self._project_dir(project_id) / "project.yaml"
        config_path.write_text(yaml.dump(project, default_flow_style=False))
        return True

    # -------------------------------------------------------------------------
    # Tasks
    # -------------------------------------------------------------------------

    def add_task(
        self,
        project_id: str,
        title: str,
        description: str,
        task_type: str = "feature",
    ) -> Optional[str]:
        """
        Add a task to a project.

        Only allowed when project is in Assess realm.

        Args:
            project_id: Project to add task to
            title: Task title
            description: Task description
            task_type: "feature" or "bug"

        Returns:
            task_id if successful, None if project not found or not in Assess
        """
        project = self.get_project(project_id)
        if not project:
            return None

        if project.get("realm") != "assess":
            return None  # Can only add tasks in Assess

        if task_type not in self.TASK_TYPES:
            task_type = "feature"

        task_id = self._generate_task_id(project_id)

        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "type": task_type,
            "status": "draft",
            "version": None,
            "branch": None,
            "execution_log": None,
            "created_at": datetime.now().isoformat(),
            "scheduled_at": None,
            "started_at": None,
            "completed_at": None,
        }

        task_path = self._task_path(project_id, task_id)
        task_path.write_text(yaml.dump(task, default_flow_style=False))

        return task_id

    def get_task(self, project_id: str, task_id: str) -> Optional[dict]:
        """Get a task by ID."""
        task_path = self._task_path(project_id, task_id)
        if not task_path.exists():
            return None

        return yaml.safe_load(task_path.read_text())

    def list_tasks(
        self,
        project_id: str,
        status: Optional[str] = None,
        version: Optional[str] = None,
    ) -> list[dict]:
        """
        List tasks for a project.

        Args:
            project_id: Project ID
            status: Filter by status
            version: Filter by version

        Returns:
            List of tasks
        """
        tasks = []
        tasks_dir = self._project_dir(project_id) / "tasks"

        if not tasks_dir.exists():
            return tasks

        for task_file in sorted(tasks_dir.glob("*.yaml")):
            task = yaml.safe_load(task_file.read_text())

            if status and task.get("status") != status:
                continue
            if version and task.get("version") != version:
                continue

            tasks.append(task)

        return tasks

    def update_task(self, project_id: str, task_id: str, **fields) -> bool:
        """
        Update task fields.

        Only allowed in Assess realm for editing content.
        Status changes have their own methods.
        """
        task = self.get_task(project_id, task_id)
        if not task:
            return False

        task.update(fields)
        task_path = self._task_path(project_id, task_id)
        task_path.write_text(yaml.dump(task, default_flow_style=False))
        return True

    def delete_task(self, project_id: str, task_id: str) -> bool:
        """
        Delete a task.

        Only allowed when project is in Assess realm.

        Returns:
            True if deleted, False if not found or not in Assess
        """
        project = self.get_project(project_id)
        if not project or project.get("realm") != "assess":
            return False

        task_path = self._task_path(project_id, task_id)
        if not task_path.exists():
            return False

        task_path.unlink()
        return True

    def mark_task_ready(self, project_id: str, task_id: str) -> bool:
        """
        Mark a task as ready (done defining).

        Only allowed in Assess realm, moves from draft to ready.
        """
        project = self.get_project(project_id)
        if not project or project.get("realm") != "assess":
            return False

        task = self.get_task(project_id, task_id)
        if not task or task.get("status") != "draft":
            return False

        return self.update_task(project_id, task_id, status="ready")

    def schedule_task(self, project_id: str, task_id: str, version: str) -> bool:
        """
        Schedule a task (assign to version).

        Only allowed in Decide realm.
        Creates version if it doesn't exist.
        """
        project = self.get_project(project_id)
        if not project or project.get("realm") != "decide":
            return False

        task = self.get_task(project_id, task_id)
        if not task or task.get("status") != "unscheduled":
            return False

        # Create version if it doesn't exist
        version_data = self.get_version(project_id, version)
        if not version_data:
            self.add_version(project_id, version)
            version_data = self.get_version(project_id, version)

        # Add task to version's task list
        if task_id not in version_data.get("tasks", []):
            version_data["tasks"] = version_data.get("tasks", []) + [task_id]
            version_path = self._version_path(project_id, version)
            version_path.write_text(yaml.dump(version_data, default_flow_style=False))

        return self.update_task(
            project_id,
            task_id,
            status="scheduled",
            version=version,
            scheduled_at=datetime.now().isoformat(),
        )

    def start_task(self, project_id: str, task_id: str, branch: Optional[str] = None) -> bool:
        """
        Start working on a task.

        Only allowed in Do realm.
        Generates branch name if not provided.
        """
        project = self.get_project(project_id)
        if not project or project.get("realm") != "do":
            return False

        task = self.get_task(project_id, task_id)
        if not task or task.get("status") != "scheduled":
            return False

        # Generate branch name if not provided
        if not branch:
            prefix = "feat" if task.get("type") == "feature" else "bug"
            slug = safe_filename(task["title"].lower().replace(" ", "-"))
            branch = f"{prefix}/{slug}"

        return self.update_task(
            project_id,
            task_id,
            status="in_progress",
            branch=branch,
            started_at=datetime.now().isoformat(),
        )

    def complete_task(self, project_id: str, task_id: str, execution_log: str) -> bool:
        """
        Mark a task as done.

        Only allowed in Do realm.
        Stores the full execution log.
        """
        project = self.get_project(project_id)
        if not project or project.get("realm") != "do":
            return False

        task = self.get_task(project_id, task_id)
        if not task or task.get("status") not in ("in_progress", "blocked"):
            return False

        return self.update_task(
            project_id,
            task_id,
            status="done",
            execution_log=execution_log,
            completed_at=datetime.now().isoformat(),
        )

    def block_task(self, project_id: str, task_id: str, reason: str) -> bool:
        """Mark a task as blocked."""
        project = self.get_project(project_id)
        if not project or project.get("realm") != "do":
            return False

        task = self.get_task(project_id, task_id)
        if not task or task.get("status") != "in_progress":
            return False

        return self.update_task(
            project_id,
            task_id,
            status="blocked",
            block_reason=reason,
        )

    def unblock_task(self, project_id: str, task_id: str) -> bool:
        """Unblock a task."""
        project = self.get_project(project_id)
        if not project or project.get("realm") != "do":
            return False

        task = self.get_task(project_id, task_id)
        if not task or task.get("status") != "blocked":
            return False

        return self.update_task(
            project_id,
            task_id,
            status="in_progress",
            block_reason=None,
        )

    # -------------------------------------------------------------------------
    # Realm Transitions
    # -------------------------------------------------------------------------

    def _log_transition(
        self,
        project_id: str,
        from_realm: str,
        to_realm: str,
        reason: Optional[str] = None,
        time_in_realm: Optional[str] = None,
    ) -> None:
        """Log a realm transition."""
        project_dir = self._project_dir(project_id)
        transitions_path = project_dir / "transitions.log"

        timestamp = datetime.now().isoformat()

        if time_in_realm:
            entry = f"{timestamp} | {from_realm} -> {to_realm} | {time_in_realm} in {from_realm}"
        else:
            entry = f"{timestamp} | {from_realm} -> {to_realm}"

        if reason:
            entry += f" | {reason}"

        entry += "\n"

        with open(transitions_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def _calculate_time_in_realm(self, project_id: str) -> str:
        """Calculate time spent in current realm."""
        project_dir = self._project_dir(project_id)
        transitions_path = project_dir / "transitions.log"

        if not transitions_path.exists():
            return "unknown"

        content = transitions_path.read_text().strip()
        if not content:
            return "unknown"

        # Get last transition timestamp
        lines = content.split("\n")
        last_line = lines[-1]

        try:
            timestamp_str = last_line.split(" | ")[0]
            last_transition = datetime.fromisoformat(timestamp_str)
            delta = datetime.now() - last_transition

            days = delta.days
            hours = delta.seconds // 3600
            minutes = (delta.seconds % 3600) // 60

            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{minutes}m"
        except (ValueError, IndexError):
            return "unknown"

    def can_move_to_decide(self, project_id: str) -> tuple[bool, list[str]]:
        """
        Check if project can move from Assess to Decide.

        All tasks must be 'ready'.

        Returns:
            (can_move, list of issues)
        """
        project = self.get_project(project_id)
        if not project:
            return False, ["Project not found"]

        if project.get("realm") != "assess":
            return False, [f"Project is in {project.get('realm')}, not assess"]

        tasks = self.list_tasks(project_id)
        if not tasks:
            return False, ["Project has no tasks"]

        issues = []
        for task in tasks:
            if task.get("status") != "ready":
                issues.append(f"Task {task['id']} '{task['title']}' is {task.get('status')}, not ready")

        return len(issues) == 0, issues

    def can_move_to_do(self, project_id: str) -> tuple[bool, list[str]]:
        """
        Check if project can move from Decide to Do.

        All tasks must be 'scheduled' (assigned to a version).

        Returns:
            (can_move, list of issues)
        """
        project = self.get_project(project_id)
        if not project:
            return False, ["Project not found"]

        if project.get("realm") != "decide":
            return False, [f"Project is in {project.get('realm')}, not decide"]

        tasks = self.list_tasks(project_id)
        if not tasks:
            return False, ["Project has no tasks"]

        issues = []
        for task in tasks:
            if task.get("status") != "scheduled":
                issues.append(f"Task {task['id']} '{task['title']}' is {task.get('status')}, not scheduled")

        return len(issues) == 0, issues

    def move_project_to_realm(
        self,
        project_id: str,
        target_realm: str,
        reason: Optional[str] = None,
    ) -> tuple[bool, list[str]]:
        """
        Move a project to a different realm.

        Forward moves (assess->decide->do) require validation.
        Backward moves are always allowed (flexible mode) but logged.

        Args:
            project_id: Project to move
            target_realm: Target realm (assess, decide, do)
            reason: Optional reason for the move

        Returns:
            (success, list of issues or empty list)
        """
        if target_realm not in self.REALMS:
            return False, [f"Invalid realm: {target_realm}"]

        project = self.get_project(project_id)
        if not project:
            return False, ["Project not found"]

        current_realm = project.get("realm")
        if current_realm == target_realm:
            return False, [f"Project is already in {target_realm}"]

        # Check forward transitions
        if current_realm == "assess" and target_realm == "decide":
            can_move, issues = self.can_move_to_decide(project_id)
            if not can_move:
                return False, issues

            # Update task statuses from 'ready' to 'unscheduled'
            for task in self.list_tasks(project_id):
                self.update_task(project_id, task["id"], status="unscheduled")

        elif current_realm == "decide" and target_realm == "do":
            can_move, issues = self.can_move_to_do(project_id)
            if not can_move:
                return False, issues

            # Find the version all tasks are scheduled for
            tasks = self.list_tasks(project_id)
            if tasks:
                version = tasks[0].get("version")
                # Activate the version
                self._update_version_status(project_id, version, "active")
                # Set current version on project
                self._update_project(project_id, current_version=version)

        # For backward moves, just log the reason (flexible mode)
        elif target_realm in ("assess", "decide") and current_realm in ("decide", "do"):
            if not reason:
                reason = "backtracked"

        # Calculate time in current realm
        time_in_realm = self._calculate_time_in_realm(project_id)

        # Log the transition
        self._log_transition(project_id, current_realm, target_realm, reason, time_in_realm)

        # Update project realm
        self._update_project(project_id, realm=target_realm)

        return True, []

    # -------------------------------------------------------------------------
    # Versions
    # -------------------------------------------------------------------------

    def add_version(self, project_id: str, version: str) -> bool:
        """
        Add a new version to a project.

        Args:
            project_id: Project ID
            version: Version string (e.g., "1.2.0")

        Returns:
            True if created, False if project not found or version exists
        """
        project = self.get_project(project_id)
        if not project:
            return False

        version_path = self._version_path(project_id, version)
        if version_path.exists():
            return False  # Version already exists

        version_data = {
            "version": version,
            "status": "planned",
            "branch": f"version/{version}",
            "tasks": [],
            "created_at": datetime.now().isoformat(),
            "released_at": None,
        }

        ensure_dir(version_path.parent)
        version_path.write_text(yaml.dump(version_data, default_flow_style=False))
        return True

    def get_version(self, project_id: str, version: str) -> Optional[dict]:
        """Get version information."""
        version_path = self._version_path(project_id, version)
        if not version_path.exists():
            return None

        return yaml.safe_load(version_path.read_text())

    def list_versions(self, project_id: str) -> list[dict]:
        """List all versions for a project."""
        versions = []
        versions_dir = self._project_dir(project_id) / "versions"

        if not versions_dir.exists():
            return versions

        for version_file in sorted(versions_dir.glob("*.yaml")):
            version_data = yaml.safe_load(version_file.read_text())
            versions.append(version_data)

        return versions

    def _update_version_status(self, project_id: str, version: str, status: str) -> bool:
        """Update version status."""
        version_data = self.get_version(project_id, version)
        if not version_data:
            return False

        version_data["status"] = status
        if status == "released":
            version_data["released_at"] = datetime.now().isoformat()

        version_path = self._version_path(project_id, version)
        version_path.write_text(yaml.dump(version_data, default_flow_style=False))
        return True

    def release_version(self, project_id: str, version: str) -> tuple[bool, list[str]]:
        """
        Release a version.

        All tasks in the version must be done.

        Returns:
            (success, issues)
        """
        version_data = self.get_version(project_id, version)
        if not version_data:
            return False, ["Version not found"]

        if version_data.get("status") != "active":
            return False, [f"Version is {version_data.get('status')}, not active"]

        # Check all tasks for this version are done
        tasks = self.list_tasks(project_id, version=version)
        issues = []
        for task in tasks:
            if task.get("status") != "done":
                issues.append(f"Task {task['id']} '{task['title']}' is {task.get('status')}, not done")

        if issues:
            return False, issues

        # Mark version as ready (user will merge to main manually)
        self._update_version_status(project_id, version, "ready")

        return True, []

    def mark_version_released(self, project_id: str, version: str) -> bool:
        """Mark a version as released (after merge to main)."""
        version_data = self.get_version(project_id, version)
        if not version_data or version_data.get("status") != "ready":
            return False

        self._update_version_status(project_id, version, "released")

        # Clear current_version on project
        self._update_project(project_id, current_version=None)

        return True

    def get_version_tasks(self, project_id: str, version: str) -> list[dict]:
        """Get all tasks assigned to a specific version."""
        return self.list_tasks(project_id, version=version)

    # -------------------------------------------------------------------------
    # Meta-cognition Support
    # -------------------------------------------------------------------------

    def get_transition_history(self, project_id: str) -> list[dict]:
        """
        Get the full transition history for a project.

        Returns:
            List of transition records with timestamp, from_realm, to_realm, duration, reason
        """
        project_dir = self._project_dir(project_id)
        transitions_path = project_dir / "transitions.log"

        if not transitions_path.exists():
            return []

        transitions = []
        content = transitions_path.read_text().strip()

        for line in content.split("\n"):
            if not line.strip():
                continue

            parts = line.split(" | ")
            if len(parts) < 2:
                continue

            record = {"timestamp": parts[0]}

            # Parse the transition
            if "created" in parts[1]:
                record["type"] = "created"
                record["realm"] = parts[1].split()[-1] if len(parts[1].split()) > 1 else "assess"
            elif "->" in parts[1]:
                record["type"] = "transition"
                realms = parts[1].split(" -> ")
                record["from_realm"] = realms[0].strip()
                record["to_realm"] = realms[1].strip()

            # Parse duration if present
            if len(parts) > 2:
                duration_part = parts[2]
                if " in " in duration_part:
                    record["duration"] = duration_part.split(" in ")[0].strip()

            # Parse reason if present
            if len(parts) > 3:
                record["reason"] = parts[3].strip()

            transitions.append(record)

        return transitions

    def get_realm_time(self, project_id: str) -> dict:
        """
        Calculate total time spent in each realm.

        Returns:
            Dict with realm names as keys and total minutes as values
        """
        history = self.get_transition_history(project_id)

        realm_times = {"assess": 0, "decide": 0, "do": 0}

        for record in history:
            if record.get("type") != "transition":
                continue

            duration_str = record.get("duration", "")
            if not duration_str:
                continue

            # Parse duration string (e.g., "3d 4h 30m", "2h 15m", "45m")
            minutes = 0
            parts = duration_str.split()
            for part in parts:
                if part.endswith("d"):
                    minutes += int(part[:-1]) * 24 * 60
                elif part.endswith("h"):
                    minutes += int(part[:-1]) * 60
                elif part.endswith("m"):
                    minutes += int(part[:-1])

            from_realm = record.get("from_realm", "")
            if from_realm in realm_times:
                realm_times[from_realm] += minutes

        # Add current realm time
        project = self.get_project(project_id)
        if project:
            current_realm = project.get("realm")
            if current_realm in realm_times:
                current_duration = self._calculate_time_in_realm(project_id)
                # Parse current duration
                minutes = 0
                parts = current_duration.split()
                for part in parts:
                    if part.endswith("d"):
                        minutes += int(part[:-1]) * 24 * 60
                    elif part.endswith("h"):
                        minutes += int(part[:-1]) * 60
                    elif part.endswith("m"):
                        minutes += int(part[:-1])
                realm_times[current_realm] += minutes

        return realm_times

    def get_stuck_projects(self, threshold_days: int = 7) -> list[dict]:
        """
        Find projects that have been in the same realm too long.

        Args:
            threshold_days: Days threshold to consider "stuck"

        Returns:
            List of project info with realm and time stuck
        """
        stuck = []
        threshold_minutes = threshold_days * 24 * 60

        for project in self.list_projects():
            project_id = project.get("id")
            current_realm = project.get("realm")

            # Get time in current realm
            duration_str = self._calculate_time_in_realm(project_id)

            # Parse to minutes
            minutes = 0
            parts = duration_str.split()
            for part in parts:
                if part.endswith("d"):
                    minutes += int(part[:-1]) * 24 * 60
                elif part.endswith("h"):
                    minutes += int(part[:-1]) * 60
                elif part.endswith("m"):
                    minutes += int(part[:-1])

            if minutes >= threshold_minutes:
                stuck.append({
                    "project_id": project_id,
                    "name": project.get("name"),
                    "realm": current_realm,
                    "time_in_realm": duration_str,
                    "minutes": minutes,
                })

        # Sort by time stuck (longest first)
        stuck.sort(key=lambda x: x["minutes"], reverse=True)
        return stuck

    def format_realm_time(self, project_id: str) -> str:
        """Format realm time as human-readable string."""
        realm_times = self.get_realm_time(project_id)
        total = sum(realm_times.values())

        if total == 0:
            return "No time tracked"

        parts = []
        for realm in ["assess", "decide", "do"]:
            minutes = realm_times[realm]
            if minutes > 0:
                pct = (minutes / total) * 100
                # Convert minutes to readable format
                if minutes >= 24 * 60:
                    days = minutes // (24 * 60)
                    hours = (minutes % (24 * 60)) // 60
                    time_str = f"{days}d {hours}h"
                elif minutes >= 60:
                    hours = minutes // 60
                    mins = minutes % 60
                    time_str = f"{hours}h {mins}m"
                else:
                    time_str = f"{minutes}m"

                parts.append(f"{realm.capitalize()}: {time_str} ({pct:.0f}%)")

        return " | ".join(parts)

    # -------------------------------------------------------------------------
    # Summary for Memory Injection
    # -------------------------------------------------------------------------

    def get_projects_summary(self) -> str:
        """
        Get a summary of all projects for memory injection.

        Returns:
            Formatted string summarizing active projects
        """
        projects = self.list_projects()

        if not projects:
            return ""

        lines = []
        for project in projects:
            project_id = project.get("id")
            name = project.get("name")
            realm = project.get("realm", "assess").capitalize()
            current_version = project.get("current_version")

            # Count tasks by status
            tasks = self.list_tasks(project_id)
            total = len(tasks)
            done = len([t for t in tasks if t.get("status") == "done"])
            in_progress = len([t for t in tasks if t.get("status") == "in_progress"])

            status_parts = []
            if in_progress > 0:
                status_parts.append(f"{in_progress} in progress")
            if done > 0 and done < total:
                status_parts.append(f"{done}/{total} done")
            elif total > 0:
                status_parts.append(f"{total} tasks")

            status = ", ".join(status_parts) if status_parts else "no tasks"

            version_str = f" v{current_version}" if current_version else ""
            lines.append(f"- {name}{version_str} ({realm}): {status}")

        return "\n".join(lines)
