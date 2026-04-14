"""Bootstrap help documentation for the Help system collection.

Each entry in HELP_PROJECTS maps to one project (section) in the Help
collection.  Its tasks become read-only info cards in the UI.
"""

from datetime import datetime
from pathlib import Path

import yaml

# Sentinel: if this project file exists, bootstrapping already ran.
HELP_SENTINEL_ID = "help-getting-started"

HELP_PROJECTS = [
    {
        "id": "help-getting-started",
        "name": "Getting Started",
        "tasks": [
            (
                "What is AIGernon?",
                "AIGernon is your cognitive companion. It helps you capture ideas, "
                "plan projects, and execute tasks — all in one place with AI assistance.",
            ),
            (
                "Navigating the app",
                "Use the sidebar to switch between Chat, Projects, Schedule, and Memory. "
                "Each area serves a distinct purpose in your workflow.",
            ),
            (
                "Instances",
                "Instances are isolated workspaces. You can have one for personal use "
                "and one for work. Switch between them using the instance selector at the top.",
            ),
        ],
    },
    {
        "id": "help-realms",
        "name": "Realms: Assess · Decide · Do",
        "tasks": [
            (
                "The Assess realm",
                "Assess is where new ideas and projects land. Capture anything here without "
                "commitment. Define tasks to clarify scope before moving forward.",
            ),
            (
                "The Decide realm",
                "When a project is worth pursuing, move it to Decide. Assign tasks to a "
                "version number (e.g. 1.0.0) to commit to their delivery.",
            ),
            (
                "The Do realm",
                "Do is the execution zone. Tasks have Start and Agent buttons. Work through "
                "them, mark them complete. When all tasks are done, mark the project as Done.",
            ),
            (
                "Collections",
                "Collections is where completed or archived projects live. Projects here are "
                "read-only. You can revive them back to Assess at any time.",
            ),
        ],
    },
    {
        "id": "help-tasks-versions",
        "name": "Tasks and Versions",
        "tasks": [
            (
                "Creating tasks",
                "In the Assess realm, use Add Task to define work items. "
                "Each task has a title, optional description, and type (Feature or Bug).",
            ),
            (
                "Assigning to a version",
                "In Decide, click 'Assign to version' on a task. Enter a version number such as "
                "1.0.0. All tasks in a version share the same git branch (version/1.0.0).",
            ),
            (
                "Starting and completing tasks",
                "In Do, click Start to begin a task (marks it In Progress). Click Complete "
                "when finished. When all version tasks are done, a PR is opened automatically.",
            ),
            (
                "Using the Agent",
                "The Agent button assigns AIGernon's AI to a task. It reads the task description "
                "and works autonomously in your git repo. Monitor progress in real time.",
            ),
        ],
    },
    {
        "id": "help-github",
        "name": "GitHub Integration",
        "tasks": [
            (
                "Linking your account",
                "Go to Settings → GitHub to connect via OAuth. This allows AIGernon to "
                "create branches and open pull requests on your behalf.",
            ),
            (
                "Repos and branches",
                "Set a repository URL on your project. When a task is assigned to a version, "
                "AIGernon creates a version/X.x.x branch from your default branch automatically.",
            ),
            (
                "Auto pull-requests",
                "When all tasks in a version are completed, AIGernon opens a pull request from "
                "version/X.x.x to your default branch, with a summary of everything that was done.",
            ),
        ],
    },
    {
        "id": "help-scheduled-jobs",
        "name": "Scheduled Jobs",
        "tasks": [
            (
                "What are scheduled jobs?",
                "Scheduled jobs let AIGernon run prompts automatically on a schedule — "
                "daily briefings, weekly reviews, or any recurring task you can describe in words.",
            ),
            (
                "Setting up a schedule",
                "In the Schedule section, click New Job. Choose a name, a recurrence "
                "(every N minutes or a cron expression), and write the message to send to AIGernon.",
            ),
            (
                "Delivery channels",
                "Each job's response can be delivered via email and/or Telegram. "
                "Configure your channels in Settings. Email uses Resend; Telegram uses a bot link.",
            ),
        ],
    },
]


def bootstrap_help_collection(workspace: Path) -> None:
    """
    Write help projects and tasks to disk if they don't already exist.
    Uses the sentinel project as a first-run detector.
    Safe to call on every startup — exits immediately after the sentinel check.
    """
    projects_dir = workspace / "projects"
    sentinel_path = projects_dir / HELP_SENTINEL_ID / "project.yaml"

    if sentinel_path.exists():
        return  # Already bootstrapped

    for proj in HELP_PROJECTS:
        proj_id = proj["id"]
        proj_dir = projects_dir / proj_id
        tasks_dir = proj_dir / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)

        project_data = {
            "name": proj["name"],
            "realm": "collections",
            "collection_id": "help",
            "help_content": True,
            "created_at": datetime.now().isoformat(),
        }
        (proj_dir / "project.yaml").write_text(
            yaml.dump(project_data, default_flow_style=False)
        )

        for i, (title, description) in enumerate(proj["tasks"], start=1):
            task_id = str(i).zfill(3)
            task_data = {
                "id": task_id,
                "title": title,
                "description": description,
                "type": "feature",
                "status": "done",
            }
            (tasks_dir / f"{task_id}.yaml").write_text(
                yaml.dump(task_data, default_flow_style=False)
            )
