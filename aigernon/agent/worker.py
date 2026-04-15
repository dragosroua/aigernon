"""Agent worker — runs the agent in a project workspace."""

from datetime import datetime
from typing import Optional

from loguru import logger

from aigernon.workspace.manager import WorkspaceManager
from aigernon.workspace.github import create_pull_request


async def run_agent_job(
    job_id: str,
    project: dict,
    task: Optional[dict],
    trigger: str,
    prompt_override: Optional[str],
    user: dict,
    agent_pool,
    workspace_manager: WorkspaceManager,
    db,
    ws_manager=None,
) -> None:
    """Execute an agent job: setup workspace, run agent, commit, push, open PR."""

    async def _update(**kwargs):
        await db.update_agent_job(job_id, **kwargs)

    async def _notify(msg: str):
        if ws_manager:
            try:
                await ws_manager.send_notification(
                    user_id=user["id"],
                    notification={"type": "agent_job", "title": "Agent job", "body": msg},
                )
            except Exception:
                pass

    await _update(status="running", started_at=datetime.utcnow().isoformat())
    logger.info(f"Agent job {job_id} starting (trigger={trigger})")

    try:
        repo_url = project.get("repo", "")

        if not repo_url:
            raise ValueError("Project has no repo URL — add one on the Projects page")

        # Resolve GitHub token: match by repo owner from linked accounts
        github_token = None
        try:
            # Parse owner from repo URL (github.com/owner/repo)
            parts = repo_url.replace("https://github.com/", "").replace("git@github.com:", "").strip("/").split("/")
            owner = parts[0] if parts else None
            if owner:
                github_token = await db.get_github_token_for_owner(user["id"], owner)
        except Exception:
            pass
        # 1. Clone / pull workspace
        project_name = project.get("name", project["id"])
        workspace = await workspace_manager.clone_or_pull(
            project_id=project["id"],
            repo_url=repo_url,
            github_token=github_token,
            name=project_name,
        )

        # 2. Create branch
        title = task["title"] if task else f"job-{job_id}"
        branch = workspace_manager.make_branch_name(title)
        await workspace_manager.create_branch(workspace, branch)
        await _update(branch=branch)
        await _notify(f"Working on branch {branch}…")

        # 3. Build prompt
        if prompt_override:
            prompt = prompt_override
        else:
            task_section = ""
            if task:
                task_section = (
                    f"## Task\n"
                    f"**Title:** {task['title']}\n"
                    f"**Type:** {task.get('type', 'feature')}\n"
                    f"**Description:** {task.get('description') or '(none provided)'}\n"
                    f"**Target version:** {task.get('version') or '(none)'}\n\n"
                )

            prompt = (
                f"You are working on a software project. "
                f"The repository is checked out at: `{workspace}`\n\n"
                f"{task_section}"
                f"## Instructions\n"
                f"1. Explore the codebase to understand the structure\n"
                f"2. Implement the changes needed for this task\n"
                f"3. Ensure changes are complete and consistent with the existing code style\n"
                f"4. Summarize what you changed and why\n\n"
                f"Work directly inside `{workspace}`. "
                f"**Do not run git commands** — committing and pushing will be handled automatically."
            )

        # 4. Run agent
        response = await agent_pool.process_direct(
            user_id=user["id"],
            content=prompt,
            session_key=f"agent_job:{job_id}",
            channel="agent_job",
            chat_id=job_id,
        )
        output = response or "(agent produced no output)"

        # 5. Commit and push
        commit_msg = (
            f"feat: {task['title']}\n\nAgent job {job_id} — trigger: {trigger}"
            if task
            else f"chore: agent job {job_id} — trigger: {trigger}"
        )
        had_changes = await workspace_manager.commit_and_push(
            workspace=workspace,
            branch=branch,
            message=commit_msg,
            author_name=user.get("name") or "AIGernon",
            author_email=user.get("email") or "aigernon@local",
            github_token=github_token,
            repo_url=repo_url,
        )

        # 6. Open PR
        pr_url = None
        if had_changes and github_token and repo_url:
            pr_title = f"[AIGernon] {task['title']}" if task else f"[AIGernon] Job {job_id}"
            pr_body = (
                f"Automated changes by AIGernon.\n\n"
                f"**Job ID:** `{job_id}`  \n"
                f"**Trigger:** {trigger}\n\n"
                f"---\n\n{output[:3000]}"
            )
            pr_url = await create_pull_request(
                repo_url=repo_url,
                token=github_token,
                branch=branch,
                title=pr_title,
                body=pr_body,
            )

        status_msg = f"PR opened: {pr_url}" if pr_url else (
            f"Branch pushed: `{branch}` (no PR — GitHub token not set)" if had_changes
            else "No changes made"
        )

        await _update(
            status="done",
            output=output,
            pr_url=pr_url,
            completed_at=datetime.utcnow().isoformat(),
        )
        await _notify(status_msg)
        logger.info(f"Agent job {job_id} done")

    except Exception as exc:
        logger.exception(f"Agent job {job_id} failed: {exc}")
        await _update(
            status="failed",
            error=str(exc),
            completed_at=datetime.utcnow().isoformat(),
        )
        await _notify(f"Job failed: {exc}")
