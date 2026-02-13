"""Coaching data store for multi-client coaching support."""

from pathlib import Path
from datetime import datetime
from typing import Optional
import re
import yaml

from aigernon.utils.helpers import ensure_dir


class CoachingStore:
    """
    Data store for coaching module.

    Manages per-client coaching data including ideas, questions,
    session notes, and emergency flags.
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.coaching_dir = ensure_dir(workspace / "coaching")

    def _client_dir(self, client_id: str) -> Path:
        """Get the directory for a specific client."""
        # Sanitize client_id for filesystem (replace : with _)
        safe_id = client_id.replace(":", "_").replace("/", "_")
        return self.coaching_dir / safe_id

    def _ensure_client_dir(self, client_id: str) -> Path:
        """Ensure client directory exists with required files."""
        client_dir = ensure_dir(self._client_dir(client_id))
        ensure_dir(client_dir / "sessions")

        # Create empty files if they don't exist
        for filename in ["ideas.md", "questions.md", "flags.md", "history.md"]:
            filepath = client_dir / filename
            if not filepath.exists():
                filepath.write_text(f"# {filename.replace('.md', '').title()}\n\n")

        return client_dir

    # -------------------------------------------------------------------------
    # Client Management
    # -------------------------------------------------------------------------

    def add_client(
        self,
        client_id: str,
        name: str,
        coach_chat_id: str,
        coach_channel: str = "telegram",
        timezone: str = "UTC",
    ) -> dict:
        """
        Add a new coaching client.

        Args:
            client_id: Unique client identifier (e.g., "telegram:123456789")
            name: Client display name
            coach_chat_id: Coach's chat ID for notifications
            coach_channel: Channel for coach notifications
            timezone: Client's timezone

        Returns:
            Client configuration dict
        """
        client_dir = self._ensure_client_dir(client_id)

        config = {
            "client_id": client_id,
            "name": name,
            "coach_chat_id": coach_chat_id,
            "coach_channel": coach_channel,
            "timezone": timezone,
            "created_at": datetime.now().isoformat(),
            "preferences": {
                "grounding_enabled": True,
                "notification_threshold": "high",
            }
        }

        config_path = client_dir / "client.yaml"
        config_path.write_text(yaml.dump(config, default_flow_style=False))

        return config

    def get_client(self, client_id: str) -> Optional[dict]:
        """Get client configuration."""
        client_dir = self._client_dir(client_id)
        config_path = client_dir / "client.yaml"

        if not config_path.exists():
            return None

        return yaml.safe_load(config_path.read_text())

    def list_clients(self) -> list[dict]:
        """List all coaching clients."""
        clients = []

        if not self.coaching_dir.exists():
            return clients

        for client_dir in self.coaching_dir.iterdir():
            if client_dir.is_dir():
                config_path = client_dir / "client.yaml"
                if config_path.exists():
                    config = yaml.safe_load(config_path.read_text())
                    clients.append(config)

        return clients

    def find_client_by_chat(self, channel: str, chat_id: str) -> Optional[dict]:
        """Find a client by their channel and chat_id."""
        client_id = f"{channel}:{chat_id}"
        return self.get_client(client_id)

    # -------------------------------------------------------------------------
    # Ideas
    # -------------------------------------------------------------------------

    def add_idea(self, client_id: str, content: str, realm: str = "assess") -> None:
        """
        Add an idea for a client.

        Args:
            client_id: Client identifier
            content: Idea content
            realm: Detected realm (assess/decide/do)
        """
        client_dir = self._ensure_client_dir(client_id)
        ideas_path = client_dir / "ideas.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        realm_emoji = {"assess": "🔴", "decide": "🟠", "do": "🟢"}.get(realm.lower(), "⚪")

        entry = f"\n## {timestamp} {realm_emoji} {realm.upper()}\n\n{content}\n\n---\n"

        with open(ideas_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def get_ideas(self, client_id: str, since_date: Optional[datetime] = None) -> str:
        """Get ideas for a client, optionally filtered by date."""
        client_dir = self._client_dir(client_id)
        ideas_path = client_dir / "ideas.md"

        if not ideas_path.exists():
            return ""

        content = ideas_path.read_text()

        if since_date is None:
            return content

        # Filter by date
        filtered_sections = []
        sections = content.split("\n## ")

        for section in sections[1:]:  # Skip header
            # Extract date from section header
            match = re.match(r"(\d{4}-\d{2}-\d{2})", section)
            if match:
                section_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                if section_date >= since_date:
                    filtered_sections.append("## " + section)

        return "\n".join(filtered_sections) if filtered_sections else ""

    # -------------------------------------------------------------------------
    # Questions
    # -------------------------------------------------------------------------

    def add_question(self, client_id: str, content: str) -> None:
        """Add a question for a client's next session."""
        client_dir = self._ensure_client_dir(client_id)
        questions_path = client_dir / "questions.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        entry = f"\n## {timestamp}\n\n{content}\n\n---\n"

        with open(questions_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def get_questions(self, client_id: str, since_date: Optional[datetime] = None) -> str:
        """Get questions for a client."""
        client_dir = self._client_dir(client_id)
        questions_path = client_dir / "questions.md"

        if not questions_path.exists():
            return ""

        content = questions_path.read_text()

        if since_date is None:
            return content

        # Filter by date (same logic as ideas)
        filtered_sections = []
        sections = content.split("\n## ")

        for section in sections[1:]:
            match = re.match(r"(\d{4}-\d{2}-\d{2})", section)
            if match:
                section_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                if section_date >= since_date:
                    filtered_sections.append("## " + section)

        return "\n".join(filtered_sections) if filtered_sections else ""

    # -------------------------------------------------------------------------
    # Emergency Flags
    # -------------------------------------------------------------------------

    def add_flag(
        self,
        client_id: str,
        message: str,
        grounding_offered: bool = False,
        coach_notified: bool = False,
    ) -> None:
        """Add an emergency flag for a client."""
        client_dir = self._ensure_client_dir(client_id)
        flags_path = client_dir / "flags.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        grounding_str = "Yes" if grounding_offered else "No"
        notified_str = "Yes" if coach_notified else "No"

        entry = f"""
## {timestamp} 🚨 FLAGGED

Client message: "{message}"
Grounding offered: {grounding_str}
Coach notified: {notified_str}

---
"""

        with open(flags_path, "a", encoding="utf-8") as f:
            f.write(entry)

    def get_flags(self, client_id: str, since_date: Optional[datetime] = None) -> str:
        """Get emergency flags for a client."""
        client_dir = self._client_dir(client_id)
        flags_path = client_dir / "flags.md"

        if not flags_path.exists():
            return ""

        content = flags_path.read_text()

        if since_date is None:
            return content

        # Filter by date
        filtered_sections = []
        sections = content.split("\n## ")

        for section in sections[1:]:
            match = re.match(r"(\d{4}-\d{2}-\d{2})", section)
            if match:
                section_date = datetime.strptime(match.group(1), "%Y-%m-%d")
                if section_date >= since_date:
                    filtered_sections.append("## " + section)

        return "\n".join(filtered_sections) if filtered_sections else ""

    def count_flags(self, client_id: str, since_date: Optional[datetime] = None) -> int:
        """Count emergency flags for a client."""
        flags_content = self.get_flags(client_id, since_date)
        return flags_content.count("🚨 FLAGGED")

    # -------------------------------------------------------------------------
    # Sessions
    # -------------------------------------------------------------------------

    def add_session(self, client_id: str, date: str, content: str) -> Path:
        """
        Add session notes for a client.

        Args:
            client_id: Client identifier
            date: Session date (YYYY-MM-DD)
            content: Session notes content

        Returns:
            Path to created session file
        """
        client_dir = self._ensure_client_dir(client_id)
        sessions_dir = client_dir / "sessions"

        session_path = sessions_dir / f"{date}.md"

        # Add header if not present
        if not content.startswith("#"):
            content = f"# Session {date}\n\n{content}"

        session_path.write_text(content)
        return session_path

    def get_session(self, client_id: str, date: str) -> Optional[str]:
        """Get session notes for a specific date."""
        client_dir = self._client_dir(client_id)
        session_path = client_dir / "sessions" / f"{date}.md"

        if not session_path.exists():
            return None

        return session_path.read_text()

    def list_sessions(self, client_id: str) -> list[str]:
        """List all session dates for a client (newest first)."""
        client_dir = self._client_dir(client_id)
        sessions_dir = client_dir / "sessions"

        if not sessions_dir.exists():
            return []

        dates = []
        for session_file in sessions_dir.glob("????-??-??.md"):
            dates.append(session_file.stem)

        return sorted(dates, reverse=True)

    def get_last_session_date(self, client_id: str) -> Optional[str]:
        """Get the date of the most recent session."""
        sessions = self.list_sessions(client_id)
        return sessions[0] if sessions else None

    def get_sessions_summary(
        self,
        client_id: str,
        since_date: Optional[datetime] = None,
        limit: int = 5,
    ) -> str:
        """Get a summary of recent sessions."""
        sessions = self.list_sessions(client_id)

        if since_date:
            since_str = since_date.strftime("%Y-%m-%d")
            sessions = [s for s in sessions if s >= since_str]

        sessions = sessions[:limit]

        if not sessions:
            return "No sessions found."

        summaries = []
        for date in sessions:
            content = self.get_session(client_id, date)
            if content:
                # Get first few lines as summary
                lines = content.strip().split("\n")
                preview = "\n".join(lines[:5])
                if len(lines) > 5:
                    preview += "\n..."
                summaries.append(f"### {date}\n{preview}")

        return "\n\n".join(summaries)

    # -------------------------------------------------------------------------
    # History & Arc
    # -------------------------------------------------------------------------

    def get_history(self, client_id: str) -> str:
        """Get the coaching arc/history for a client."""
        client_dir = self._client_dir(client_id)
        history_path = client_dir / "history.md"

        if not history_path.exists():
            return ""

        return history_path.read_text()

    def update_history(self, client_id: str, content: str) -> None:
        """Update the coaching arc/history for a client."""
        client_dir = self._ensure_client_dir(client_id)
        history_path = client_dir / "history.md"
        history_path.write_text(content)

    # -------------------------------------------------------------------------
    # Prep (Pre-session summary)
    # -------------------------------------------------------------------------

    def get_prep_summary(self, client_id: str) -> dict:
        """
        Get a pre-session preparation summary.

        Returns dict with:
            - client: client config
            - last_session: date of last session
            - ideas: ideas since last session
            - questions: questions since last session
            - flags: flags since last session
            - flag_count: number of flags
        """
        client = self.get_client(client_id)
        if not client:
            return {"error": f"Client {client_id} not found"}

        last_session = self.get_last_session_date(client_id)
        since_date = None

        if last_session:
            since_date = datetime.strptime(last_session, "%Y-%m-%d")

        return {
            "client": client,
            "last_session": last_session,
            "ideas": self.get_ideas(client_id, since_date),
            "questions": self.get_questions(client_id, since_date),
            "flags": self.get_flags(client_id, since_date),
            "flag_count": self.count_flags(client_id, since_date),
            "history": self.get_history(client_id),
        }

    def format_prep_summary(self, client_id: str) -> str:
        """Format a human-readable prep summary."""
        prep = self.get_prep_summary(client_id)

        if "error" in prep:
            return prep["error"]

        client = prep["client"]
        lines = [
            f"# Pre-Session Prep: {client['name']}",
            f"Client ID: {client['client_id']}",
            f"Last session: {prep['last_session'] or 'None recorded'}",
            "",
        ]

        # Flags (urgent)
        if prep["flag_count"] > 0:
            lines.append(f"## 🚨 Flags ({prep['flag_count']})")
            lines.append(prep["flags"])
            lines.append("")

        # Questions
        if prep["questions"].strip():
            lines.append("## Questions for This Session")
            lines.append(prep["questions"])
            lines.append("")

        # Ideas
        if prep["ideas"].strip():
            lines.append("## Ideas Captured")
            lines.append(prep["ideas"])
            lines.append("")

        # History summary
        if prep["history"].strip():
            lines.append("## Coaching Arc")
            # Just show first section of history
            history_preview = "\n".join(prep["history"].split("\n")[:15])
            lines.append(history_preview)

        return "\n".join(lines)
