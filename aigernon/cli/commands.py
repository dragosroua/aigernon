"""CLI commands for aigernon."""

import asyncio
import atexit
import os
import signal
from pathlib import Path
import select
import sys

import typer
from rich.console import Console
from rich.table import Table

from aigernon import __version__, __logo__

app = typer.Typer(
    name="aigernon",
    help=f"{__logo__} aigernon - Personal AI Assistant",
    no_args_is_help=True,
)

console = Console()

# ---------------------------------------------------------------------------
# Lightweight CLI input: readline for arrow keys / history, termios for flush
# ---------------------------------------------------------------------------

_READLINE = None
_HISTORY_FILE: Path | None = None
_HISTORY_HOOK_REGISTERED = False
_USING_LIBEDIT = False
_SAVED_TERM_ATTRS = None  # original termios settings, restored on exit


def _flush_pending_tty_input() -> None:
    """Drop unread keypresses typed while the model was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    except Exception:
        pass

    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return


def _save_history() -> None:
    if _READLINE is None or _HISTORY_FILE is None:
        return
    try:
        _READLINE.write_history_file(str(_HISTORY_FILE))
    except Exception:
        return


def _restore_terminal() -> None:
    """Restore terminal to its original state (echo, line buffering, etc.)."""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass


def _enable_line_editing() -> None:
    """Enable readline for arrow keys, line editing, and persistent history."""
    global _READLINE, _HISTORY_FILE, _HISTORY_HOOK_REGISTERED, _USING_LIBEDIT, _SAVED_TERM_ATTRS

    # Save terminal state before readline touches it
    try:
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

    history_file = Path.home() / ".aigernon" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    _HISTORY_FILE = history_file

    try:
        import readline
    except ImportError:
        return

    _READLINE = readline
    _USING_LIBEDIT = "libedit" in (readline.__doc__ or "").lower()

    try:
        if _USING_LIBEDIT:
            readline.parse_and_bind("bind ^I rl_complete")
        else:
            readline.parse_and_bind("tab: complete")
        readline.parse_and_bind("set editing-mode emacs")
    except Exception:
        pass

    try:
        readline.read_history_file(str(history_file))
    except Exception:
        pass

    if not _HISTORY_HOOK_REGISTERED:
        atexit.register(_save_history)
        _HISTORY_HOOK_REGISTERED = True


def _prompt_text() -> str:
    """Build a readline-friendly colored prompt."""
    if _READLINE is None:
        return "You: "
    # libedit on macOS does not honor GNU readline non-printing markers.
    if _USING_LIBEDIT:
        return "\033[1;34mYou:\033[0m "
    return "\001\033[1;34m\002You:\001\033[0m\002 "


async def _read_interactive_input_async() -> str:
    """Read user input with arrow keys and history (runs input() in a thread)."""
    try:
        return await asyncio.to_thread(input, _prompt_text())
    except EOFError as exc:
        raise KeyboardInterrupt from exc


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} aigernon v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """aigernon - Personal AI Assistant."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize aigernon configuration and workspace."""
    from aigernon.config.loader import get_config_path, save_config
    from aigernon.config.schema import Config
    from aigernon.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()
    
    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} aigernon is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.aigernon/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]aigernon agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/aigernon#-chat-apps[/dim]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
""",
        "SOUL.md": """# Soul

I am AIGernon, a cognitive companion operating on the Assess-Decide-Do framework.

## Philosophy

I don't automate thinking — I augment it. Each conversation is a cognitive partnership.

## Personality

- Warm and present
- Patient with exploration, supportive of commitment
- Celebratory of completions as new beginnings

## Values

- Honor the user's current cognitive realm
- Support natural flow between Assess, Decide, and Do
- Treat completions as livelines, not deadlines
- Be a companion, not a task bot
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")
    
    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")


def _make_provider(config):
    """Create LiteLLMProvider from config. Exits if no API key found."""
    from aigernon.providers.litellm_provider import LiteLLMProvider
    p = config.get_provider()
    model = config.agents.defaults.model
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.aigernon/config.json under providers section")
        raise typer.Exit(1)
    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        provider_name=config.get_provider_name(),
    )


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the aigernon gateway."""
    from aigernon.config.loader import load_config, get_data_dir
    from aigernon.bus.queue import MessageBus
    from aigernon.agent.loop import AgentLoop
    from aigernon.channels.manager import ChannelManager
    from aigernon.session.manager import SessionManager
    from aigernon.cron.service import CronService
    from aigernon.cron.types import CronJob
    from aigernon.heartbeat.service import HeartbeatService
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    console.print(f"{__logo__} Starting aigernon gateway on port {port}...")
    
    config = load_config()
    bus = MessageBus()
    provider = _make_provider(config)
    session_manager = SessionManager(config.workspace_path)
    
    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        max_iterations=config.agents.defaults.max_tool_iterations,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        cron_service=cron,
        restrict_to_workspace=config.tools.restrict_to_workspace,
        session_manager=session_manager,
    )
    
    # Set cron callback (needs agent)
    async def on_cron_job(job: CronJob) -> str | None:
        """Execute a cron job through the agent."""
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            from aigernon.bus.events import OutboundMessage
            await bus.publish_outbound(OutboundMessage(
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to,
                content=response or ""
            ))
        return response
    cron.on_job = on_cron_job
    
    # Create heartbeat service
    async def on_heartbeat(prompt: str) -> str:
        """Execute heartbeat through the agent."""
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True
    )
    
    # Create channel manager
    channels = ChannelManager(config, bus, session_manager=session_manager)
    
    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")
    
    console.print(f"[green]✓[/green] Heartbeat: every 30m")
    
    async def run():
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Interact with the agent directly."""
    from aigernon.config.loader import load_config
    from aigernon.bus.queue import MessageBus
    from aigernon.agent.loop import AgentLoop
    
    config = load_config()
    
    bus = MessageBus()
    provider = _make_provider(config)
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        brave_api_key=config.tools.web.search.api_key or None,
        exec_config=config.tools.exec,
        restrict_to_workspace=config.tools.restrict_to_workspace,
    )
    
    if message:
        # Single message mode
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            console.print(f"\n{__logo__} {response}")
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        _enable_line_editing()
        console.print(f"{__logo__} Interactive mode (Ctrl+C to exit)\n")

        # input() runs in a worker thread that can't be cancelled.
        # Without this handler, asyncio.run() would hang waiting for it.
        def _exit_on_sigint(signum, frame):
            _save_history()
            _restore_terminal()
            console.print("\nGoodbye!")
            os._exit(0)

        signal.signal(signal.SIGINT, _exit_on_sigint)
        
        async def run_interactive():
            while True:
                try:
                    _flush_pending_tty_input()
                    user_input = await _read_interactive_input_async()
                    if not user_input.strip():
                        continue
                    
                    response = await agent_loop.process_direct(user_input, session_id)
                    console.print(f"\n{__logo__} {response}\n")
                except KeyboardInterrupt:
                    _save_history()
                    _restore_terminal()
                    console.print("\nGoodbye!")
                    break
        
        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from aigernon.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # WhatsApp
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    dc = config.channels.discord
    table.add_row(
        "Discord",
        "✓" if dc.enabled else "✗",
        dc.gateway_url
    )
    
    # Telegram
    tg = config.channels.telegram
    tg_config = f"token: {tg.token[:10]}..." if tg.token else "[dim]not configured[/dim]"
    table.add_row(
        "Telegram",
        "✓" if tg.enabled else "✗",
        tg_config
    )

    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess
    
    # User's bridge location
    user_bridge = Path.home() / ".aigernon" / "bridge"
    
    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)
    
    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # aigernon/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall aigernon")
        raise typer.Exit(1)
    
    console.print(f"{__logo__} Setting up bridge...")
    
    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess
    
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from aigernon.config.loader import get_data_dir
    from aigernon.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("No scheduled jobs.")
        return
    
    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")
    
    import time
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"
        
        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time
        
        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'telegram', 'whatsapp')"),
):
    """Add a scheduled job."""
    from aigernon.config.loader import get_data_dir
    from aigernon.cron.service import CronService
    from aigernon.cron.types import CronSchedule
    
    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )
    
    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from aigernon.config.loader import get_data_dir
    from aigernon.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from aigernon.config.loader import get_data_dir
    from aigernon.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from aigernon.config.loader import get_data_dir
    from aigernon.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    async def run():
        return await service.run_job(job_id, force=force)
    
    if asyncio.run(run()):
        console.print(f"[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show aigernon status."""
    from aigernon.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} aigernon Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        from aigernon.providers.registry import PROVIDERS

        console.print(f"Model: {config.agents.defaults.model}")
        
        # Check API keys from registry
        for spec in PROVIDERS:
            p = getattr(config.providers, spec.name, None)
            if p is None:
                continue
            if spec.is_local:
                # Local deployments show api_base instead of api_key
                if p.api_base:
                    console.print(f"{spec.label}: [green]✓ {p.api_base}[/green]")
                else:
                    console.print(f"{spec.label}: [dim]not set[/dim]")
            else:
                has_key = bool(p.api_key)
                console.print(f"{spec.label}: {'[green]✓[/green]' if has_key else '[dim]not set[/dim]'}")


# ============================================================================
# Projects Commands
# ============================================================================

ideas_app = typer.Typer(help="Brainstorming ideas (always in Assess)")
app.add_typer(ideas_app, name="ideas")

projects_app = typer.Typer(help="iOS project management with ADD workflow")
app.add_typer(projects_app, name="projects")

tasks_app = typer.Typer(help="Task management within projects")
app.add_typer(tasks_app, name="tasks")

versions_app = typer.Typer(help="Version management for projects")
app.add_typer(versions_app, name="versions")


# --- Ideas Commands ---

@ideas_app.command("list")
def ideas_list():
    """List all ideas."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    ideas = store.list_ideas()

    if not ideas:
        console.print("No ideas yet.")
        console.print("Add one with: [cyan]aigernon ideas add \"My Idea\"[/cyan]")
        return

    table = Table(title="Ideas")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Items", justify="right")

    for idea in ideas:
        table.add_row(
            idea["id"],
            idea["title"],
            str(len(idea["items"])),
        )

    console.print(table)


@ideas_app.command("add")
def ideas_add(title: str = typer.Argument(..., help="Idea title")):
    """Add a new idea."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    idea_id = store.add_idea(title)
    console.print(f"[green]✓[/green] Created idea: {idea_id}")


@ideas_app.command("show")
def ideas_show(idea_id: str = typer.Argument(..., help="Idea ID")):
    """Show an idea with its items."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    idea = store.get_idea(idea_id)
    if not idea:
        console.print(f"[red]Idea {idea_id} not found[/red]")
        raise typer.Exit(1)

    console.print(f"# {idea['title']}\n")
    if idea["items"]:
        for i, item in enumerate(idea["items"]):
            console.print(f"  {i}. {item}")
    else:
        console.print("  [dim]No items yet[/dim]")


@ideas_app.command("add-item")
def ideas_add_item(
    idea_id: str = typer.Argument(..., help="Idea ID"),
    item: str = typer.Argument(..., help="Item to add"),
):
    """Add an item to an idea."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    if not store.add_idea_item(idea_id, item):
        console.print(f"[red]Idea {idea_id} not found[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Added item to {idea_id}")


@ideas_app.command("convert")
def ideas_convert(
    idea_id: str = typer.Argument(..., help="Idea ID to convert"),
    repo: str = typer.Option(..., "--repo", "-r", help="Git repository URL"),
):
    """Convert an idea to a project."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    project_id = store.convert_idea_to_project(idea_id, repo)
    if not project_id:
        console.print(f"[red]Idea {idea_id} not found[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Converted to project: {project_id}")
    console.print(f"  Realm: [cyan]Assess[/cyan]")


@ideas_app.command("delete")
def ideas_delete(idea_id: str = typer.Argument(..., help="Idea ID to delete")):
    """Delete an idea."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    if not store.delete_idea(idea_id):
        console.print(f"[red]Idea {idea_id} not found[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Deleted idea: {idea_id}")


# --- Projects Commands ---

@projects_app.command("list")
def projects_list(
    realm: str = typer.Option(None, "--realm", "-r", help="Filter by realm (assess/decide/do)"),
):
    """List all projects."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    projects = store.list_projects(realm=realm)

    if not projects:
        console.print("No projects yet.")
        console.print("Add one with: [cyan]aigernon projects add \"My App\" --repo <url>[/cyan]")
        return

    table = Table(title="Projects")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Realm")
    table.add_column("Version")
    table.add_column("Tasks", justify="right")

    realm_colors = {"assess": "red", "decide": "yellow", "do": "green"}

    for project in projects:
        project_id = project.get("id", "")
        realm_val = project.get("realm", "assess")
        realm_display = f"[{realm_colors.get(realm_val, 'white')}]{realm_val.capitalize()}[/]"
        version = project.get("current_version") or "-"

        tasks = store.list_tasks(project_id)
        task_count = str(len(tasks))

        table.add_row(
            project_id,
            project.get("name", ""),
            realm_display,
            version,
            task_count,
        )

    console.print(table)


@projects_app.command("add")
def projects_add(
    name: str = typer.Argument(..., help="Project name"),
    repo: str = typer.Option(..., "--repo", "-r", help="Git repository URL"),
):
    """Add a new project."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    project_id = store.add_project(name, repo)
    console.print(f"[green]✓[/green] Created project: {project_id}")
    console.print(f"  Realm: [red]Assess[/red]")
    console.print(f"  Repo: {repo}")


@projects_app.command("show")
def projects_show(project_id: str = typer.Argument(..., help="Project ID")):
    """Show project details."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    project = store.get_project(project_id)
    if not project:
        console.print(f"[red]Project {project_id} not found[/red]")
        raise typer.Exit(1)

    realm_colors = {"assess": "red", "decide": "yellow", "do": "green"}
    realm = project.get("realm", "assess")

    console.print(f"# {project.get('name')}")
    console.print(f"  ID: {project_id}")
    console.print(f"  Realm: [{realm_colors.get(realm, 'white')}]{realm.capitalize()}[/]")
    console.print(f"  Repo: {project.get('repo')}")

    if project.get("current_version"):
        console.print(f"  Version: {project.get('current_version')}")

    # Show realm time analysis
    console.print(f"\n  Time: {store.format_realm_time(project_id)}")

    # Show tasks summary
    tasks = store.list_tasks(project_id)
    if tasks:
        console.print(f"\n## Tasks ({len(tasks)})")
        for task in tasks:
            status = task.get("status", "draft")
            status_icons = {
                "draft": "○",
                "ready": "◉",
                "unscheduled": "◎",
                "scheduled": "●",
                "in_progress": "▶",
                "blocked": "■",
                "done": "✓",
            }
            icon = status_icons.get(status, "?")
            version = f" (v{task.get('version')})" if task.get("version") else ""
            console.print(f"  {icon} {task['id']}: {task['title']}{version}")


@projects_app.command("move")
def projects_move(
    project_id: str = typer.Argument(..., help="Project ID"),
    target_realm: str = typer.Argument(..., help="Target realm (assess/decide/do)"),
    reason: str = typer.Option(None, "--reason", "-r", help="Reason for move (required for backtracking)"),
):
    """Move project to a different realm."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    success, issues = store.move_project_to_realm(project_id, target_realm, reason)

    if not success:
        console.print(f"[red]Cannot move project:[/red]")
        for issue in issues:
            console.print(f"  - {issue}")
        raise typer.Exit(1)

    realm_colors = {"assess": "red", "decide": "yellow", "do": "green"}
    console.print(f"[green]✓[/green] Moved project to [{realm_colors.get(target_realm, 'white')}]{target_realm.capitalize()}[/]")


@projects_app.command("stuck")
def projects_stuck(
    days: int = typer.Option(7, "--days", "-d", help="Days threshold"),
):
    """Show projects stuck in a realm too long."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    stuck = store.get_stuck_projects(days)

    if not stuck:
        console.print(f"No projects stuck for more than {days} days.")
        return

    table = Table(title=f"Projects Stuck > {days} Days")
    table.add_column("Project", style="cyan")
    table.add_column("Realm")
    table.add_column("Time in Realm")

    realm_colors = {"assess": "red", "decide": "yellow", "do": "green"}

    for p in stuck:
        realm = p.get("realm", "assess")
        realm_display = f"[{realm_colors.get(realm, 'white')}]{realm.capitalize()}[/]"
        table.add_row(p["name"], realm_display, p["time_in_realm"])

    console.print(table)


# --- Tasks Commands ---

@tasks_app.command("list")
def tasks_list(
    project_id: str = typer.Argument(..., help="Project ID"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    version: str = typer.Option(None, "--version", "-v", help="Filter by version"),
):
    """List tasks for a project."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    project = store.get_project(project_id)
    if not project:
        console.print(f"[red]Project {project_id} not found[/red]")
        raise typer.Exit(1)

    tasks = store.list_tasks(project_id, status=status, version=version)

    if not tasks:
        console.print(f"No tasks in project {project_id}.")
        return

    table = Table(title=f"Tasks: {project.get('name')}")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Version")

    status_colors = {
        "draft": "dim",
        "ready": "white",
        "unscheduled": "yellow",
        "scheduled": "cyan",
        "in_progress": "blue",
        "blocked": "red",
        "done": "green",
    }

    for task in tasks:
        status_val = task.get("status", "draft")
        status_display = f"[{status_colors.get(status_val, 'white')}]{status_val}[/]"
        version_val = task.get("version") or "-"

        table.add_row(
            task["id"],
            task["title"],
            task.get("type", "feature"),
            status_display,
            version_val,
        )

    console.print(table)


@tasks_app.command("add")
def tasks_add(
    project_id: str = typer.Argument(..., help="Project ID"),
    title: str = typer.Argument(..., help="Task title"),
    description: str = typer.Option("", "--desc", "-d", help="Task description"),
    task_type: str = typer.Option("feature", "--type", "-t", help="Task type (feature/bug)"),
):
    """Add a task to a project (only in Assess)."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    task_id = store.add_task(project_id, title, description, task_type)
    if not task_id:
        project = store.get_project(project_id)
        if not project:
            console.print(f"[red]Project {project_id} not found[/red]")
        else:
            console.print(f"[red]Cannot add tasks in {project.get('realm')} realm (only Assess)[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Added task {task_id}: {title}")


@tasks_app.command("show")
def tasks_show(
    project_id: str = typer.Argument(..., help="Project ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Show task details."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    task = store.get_task(project_id, task_id)
    if not task:
        console.print(f"[red]Task {task_id} not found in project {project_id}[/red]")
        raise typer.Exit(1)

    console.print(f"# {task['title']}")
    console.print(f"  ID: {task['id']}")
    console.print(f"  Type: {task.get('type', 'feature')}")
    console.print(f"  Status: {task.get('status', 'draft')}")

    if task.get("version"):
        console.print(f"  Version: {task['version']}")
    if task.get("branch"):
        console.print(f"  Branch: {task['branch']}")
    if task.get("description"):
        console.print(f"\n## Description\n{task['description']}")
    if task.get("execution_log"):
        console.print(f"\n## Execution Log\n{task['execution_log']}")


@tasks_app.command("ready")
def tasks_ready(
    project_id: str = typer.Argument(..., help="Project ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
):
    """Mark a task as ready (done defining)."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    if not store.mark_task_ready(project_id, task_id):
        console.print(f"[red]Cannot mark task ready (check project realm and task status)[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Task {task_id} marked ready")


@tasks_app.command("schedule")
def tasks_schedule(
    project_id: str = typer.Argument(..., help="Project ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    version: str = typer.Option(..., "--version", "-v", help="Version to assign"),
):
    """Schedule a task (assign to version, only in Decide)."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    if not store.schedule_task(project_id, task_id, version):
        console.print(f"[red]Cannot schedule task (check project realm and task status)[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Scheduled task {task_id} for version {version}")


@tasks_app.command("start")
def tasks_start(
    project_id: str = typer.Argument(..., help="Project ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    branch: str = typer.Option(None, "--branch", "-b", help="Branch name (auto-generated if not provided)"),
):
    """Start working on a task (only in Do)."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    if not store.start_task(project_id, task_id, branch):
        console.print(f"[red]Cannot start task (check project realm and task status)[/red]")
        raise typer.Exit(1)

    task = store.get_task(project_id, task_id)
    console.print(f"[green]✓[/green] Started task {task_id}")
    console.print(f"  Branch: {task.get('branch')}")


@tasks_app.command("done")
def tasks_done(
    project_id: str = typer.Argument(..., help="Project ID"),
    task_id: str = typer.Argument(..., help="Task ID"),
    log_file: Path = typer.Option(None, "--log", "-l", help="Read execution log from file"),
):
    """Mark a task as done."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    # Get execution log
    if log_file:
        if not log_file.exists():
            console.print(f"[red]Log file not found: {log_file}[/red]")
            raise typer.Exit(1)
        execution_log = log_file.read_text()
    else:
        console.print("Enter execution log (Ctrl+D when done):")
        import sys
        lines = []
        try:
            for line in sys.stdin:
                lines.append(line)
        except EOFError:
            pass
        execution_log = "".join(lines)

    if not store.complete_task(project_id, task_id, execution_log):
        console.print(f"[red]Cannot complete task (check project realm and task status)[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Task {task_id} completed")


# --- Versions Commands ---

@versions_app.command("list")
def versions_list(project_id: str = typer.Argument(..., help="Project ID")):
    """List versions for a project."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    project = store.get_project(project_id)
    if not project:
        console.print(f"[red]Project {project_id} not found[/red]")
        raise typer.Exit(1)

    versions = store.list_versions(project_id)

    if not versions:
        console.print(f"No versions in project {project_id}.")
        return

    table = Table(title=f"Versions: {project.get('name')}")
    table.add_column("Version", style="cyan")
    table.add_column("Status")
    table.add_column("Branch")
    table.add_column("Tasks", justify="right")

    status_colors = {
        "planned": "dim",
        "active": "blue",
        "ready": "green",
        "released": "cyan",
    }

    for v in versions:
        status = v.get("status", "planned")
        status_display = f"[{status_colors.get(status, 'white')}]{status}[/]"

        table.add_row(
            v["version"],
            status_display,
            v.get("branch", ""),
            str(len(v.get("tasks", []))),
        )

    console.print(table)


@versions_app.command("add")
def versions_add(
    project_id: str = typer.Argument(..., help="Project ID"),
    version: str = typer.Argument(..., help="Version string (e.g., 1.2.0)"),
):
    """Add a new version to a project."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    if not store.add_version(project_id, version):
        console.print(f"[red]Cannot add version (project not found or version exists)[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Added version {version}")
    console.print(f"  Branch: version/{version}")


@versions_app.command("show")
def versions_show(
    project_id: str = typer.Argument(..., help="Project ID"),
    version: str = typer.Argument(..., help="Version string"),
):
    """Show version details."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    v = store.get_version(project_id, version)
    if not v:
        console.print(f"[red]Version {version} not found in project {project_id}[/red]")
        raise typer.Exit(1)

    console.print(f"# Version {v['version']}")
    console.print(f"  Status: {v.get('status', 'planned')}")
    console.print(f"  Branch: {v.get('branch')}")

    # Show tasks
    task_ids = v.get("tasks", [])
    if task_ids:
        console.print(f"\n## Tasks ({len(task_ids)})")
        for task_id in task_ids:
            task = store.get_task(project_id, task_id)
            if task:
                status_icon = "✓" if task.get("status") == "done" else "○"
                console.print(f"  {status_icon} {task_id}: {task['title']}")


@versions_app.command("release")
def versions_release(
    project_id: str = typer.Argument(..., help="Project ID"),
    version: str = typer.Argument(..., help="Version string"),
):
    """Mark a version as ready for release (all tasks must be done)."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    success, issues = store.release_version(project_id, version)

    if not success:
        console.print(f"[red]Cannot release version:[/red]")
        for issue in issues:
            console.print(f"  - {issue}")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Version {version} ready for release")
    console.print(f"  Merge branch version/{version} to main")


@versions_app.command("mark-released")
def versions_mark_released(
    project_id: str = typer.Argument(..., help="Project ID"),
    version: str = typer.Argument(..., help="Version string"),
):
    """Mark a version as released (after merging to main)."""
    from aigernon.config.loader import load_config
    from aigernon.projects.store import ProjectStore

    config = load_config()
    store = ProjectStore(config.workspace_path)

    if not store.mark_version_released(project_id, version):
        console.print(f"[red]Cannot mark released (version must be in 'ready' status)[/red]")
        raise typer.Exit(1)

    console.print(f"[green]✓[/green] Version {version} marked as released")


# ============================================================================
# Coaching Commands
# ============================================================================

coaching_app = typer.Typer(help="Coaching assistant for between-session support")
app.add_typer(coaching_app, name="coaching")


@coaching_app.command("list")
def coaching_list():
    """List all coaching clients."""
    from aigernon.config.loader import load_config
    from aigernon.coaching.store import CoachingStore

    config = load_config()
    store = CoachingStore(config.workspace_path)

    clients = store.list_clients()

    if not clients:
        console.print("No coaching clients configured.")
        console.print("Add one with: [cyan]aigernon coaching add-client[/cyan]")
        return

    table = Table(title="Coaching Clients")
    table.add_column("Client ID", style="cyan")
    table.add_column("Name")
    table.add_column("Coach Chat ID")
    table.add_column("Created")

    for client in clients:
        created = client.get("created_at", "")[:10]
        table.add_row(
            client.get("client_id", ""),
            client.get("name", ""),
            client.get("coach_chat_id", ""),
            created,
        )

    console.print(table)


@coaching_app.command("add-client")
def coaching_add_client(
    client_id: str = typer.Option(..., "--id", "-i", help="Client ID (e.g., telegram:123456789)"),
    name: str = typer.Option(..., "--name", "-n", help="Client display name"),
    coach_chat_id: str = typer.Option(..., "--coach-chat-id", "-c", help="Coach's chat ID for alerts"),
    coach_channel: str = typer.Option("telegram", "--coach-channel", help="Channel for coach notifications"),
    timezone: str = typer.Option("UTC", "--timezone", "-t", help="Client's timezone"),
):
    """Add a new coaching client."""
    from aigernon.config.loader import load_config
    from aigernon.coaching.store import CoachingStore

    config = load_config()
    store = CoachingStore(config.workspace_path)

    # Check if client already exists
    existing = store.get_client(client_id)
    if existing:
        console.print(f"[yellow]Client {client_id} already exists[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()

    client = store.add_client(
        client_id=client_id,
        name=name,
        coach_chat_id=coach_chat_id,
        coach_channel=coach_channel,
        timezone=timezone,
    )

    console.print(f"[green]✓[/green] Added client '{name}' ({client_id})")
    console.print(f"  Coach notifications: {coach_channel}:{coach_chat_id}")


@coaching_app.command("add-session")
def coaching_add_session(
    client_id: str = typer.Option(..., "--client", "-c", help="Client ID"),
    date: str = typer.Option(None, "--date", "-d", help="Session date (YYYY-MM-DD, default: today)"),
    file: Path = typer.Option(None, "--file", "-f", help="Read notes from file"),
):
    """Add session notes for a client."""
    from aigernon.config.loader import load_config
    from aigernon.coaching.store import CoachingStore
    from aigernon.utils.helpers import today_date

    config = load_config()
    store = CoachingStore(config.workspace_path)

    # Verify client exists
    client = store.get_client(client_id)
    if not client:
        console.print(f"[red]Client {client_id} not found[/red]")
        console.print("Add with: [cyan]aigernon coaching add-client --id {client_id}[/cyan]")
        raise typer.Exit(1)

    # Default to today
    if not date:
        date = today_date()

    # Get content from file or interactive input
    if file:
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        content = file.read_text()
    else:
        console.print(f"Enter session notes for {client['name']} ({date}).")
        console.print("Press Ctrl+D (Unix) or Ctrl+Z (Windows) when done.\n")

        import sys
        lines = []
        try:
            for line in sys.stdin:
                lines.append(line)
        except EOFError:
            pass
        content = "".join(lines)

    if not content.strip():
        console.print("[yellow]No content provided, aborting.[/yellow]")
        raise typer.Exit()

    session_path = store.add_session(client_id, date, content)
    console.print(f"[green]✓[/green] Added session notes: {session_path}")


@coaching_app.command("prep")
def coaching_prep(
    client_id: str = typer.Option(..., "--client", "-c", help="Client ID"),
):
    """Show pre-session preparation summary."""
    from aigernon.config.loader import load_config
    from aigernon.coaching.store import CoachingStore

    config = load_config()
    store = CoachingStore(config.workspace_path)

    # Verify client exists
    client = store.get_client(client_id)
    if not client:
        console.print(f"[red]Client {client_id} not found[/red]")
        raise typer.Exit(1)

    summary = store.format_prep_summary(client_id)
    console.print(summary)


@coaching_app.command("history")
def coaching_history(
    client_id: str = typer.Option(..., "--client", "-c", help="Client ID"),
    days: int = typer.Option(30, "--days", "-d", help="Days to look back"),
):
    """View client coaching history."""
    from datetime import datetime, timedelta
    from aigernon.config.loader import load_config
    from aigernon.coaching.store import CoachingStore

    config = load_config()
    store = CoachingStore(config.workspace_path)

    # Verify client exists
    client = store.get_client(client_id)
    if not client:
        console.print(f"[red]Client {client_id} not found[/red]")
        raise typer.Exit(1)

    since_date = datetime.now() - timedelta(days=days)

    console.print(f"# History: {client['name']}")
    console.print(f"Last {days} days\n")

    # Sessions
    console.print("## Sessions")
    sessions_summary = store.get_sessions_summary(client_id, since_date)
    console.print(sessions_summary)
    console.print()

    # Ideas
    console.print("## Ideas")
    ideas = store.get_ideas(client_id, since_date)
    console.print(ideas if ideas.strip() else "No ideas captured.")
    console.print()

    # Questions
    console.print("## Questions")
    questions = store.get_questions(client_id, since_date)
    console.print(questions if questions.strip() else "No questions recorded.")
    console.print()

    # Flags
    flag_count = store.count_flags(client_id, since_date)
    if flag_count > 0:
        console.print(f"## Flags ({flag_count})")
        flags = store.get_flags(client_id, since_date)
        console.print(flags)


if __name__ == "__main__":
    app()
