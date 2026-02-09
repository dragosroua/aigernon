"""Memory system for persistent agent memory with ADD realm tracking."""

from pathlib import Path
from datetime import datetime
from collections import Counter
import re

from aigernon.utils.helpers import ensure_dir, today_date


class MemoryStore:
    """
    Memory system for the agent.
    
    Supports daily notes (memory/YYYY-MM-DD.md) and long-term memory (MEMORY.md).
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
    
    def get_today_file(self) -> Path:
        """Get path to today's memory file."""
        return self.memory_dir / f"{today_date()}.md"
    
    def read_today(self) -> str:
        """Read today's memory notes."""
        today_file = self.get_today_file()
        if today_file.exists():
            return today_file.read_text(encoding="utf-8")
        return ""
    
    def append_today(self, content: str) -> None:
        """Append content to today's memory notes."""
        today_file = self.get_today_file()
        
        if today_file.exists():
            existing = today_file.read_text(encoding="utf-8")
            content = existing + "\n" + content
        else:
            # Add header for new day
            header = f"# {today_date()}\n\n"
            content = header + content
        
        today_file.write_text(content, encoding="utf-8")
    
    def read_long_term(self) -> str:
        """Read long-term memory (MEMORY.md)."""
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""
    
    def write_long_term(self, content: str) -> None:
        """Write to long-term memory (MEMORY.md)."""
        self.memory_file.write_text(content, encoding="utf-8")
    
    def get_recent_memories(self, days: int = 7) -> str:
        """
        Get memories from the last N days.
        
        Args:
            days: Number of days to look back.
        
        Returns:
            Combined memory content.
        """
        from datetime import timedelta
        
        memories = []
        today = datetime.now().date()
        
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.memory_dir / f"{date_str}.md"
            
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                memories.append(content)
        
        return "\n\n---\n\n".join(memories)
    
    def list_memory_files(self) -> list[Path]:
        """List all memory files sorted by date (newest first)."""
        if not self.memory_dir.exists():
            return []
        
        files = list(self.memory_dir.glob("????-??-??.md"))
        return sorted(files, reverse=True)
    
    def get_memory_context(self) -> str:
        """
        Get memory context for the agent.
        
        Returns:
            Formatted memory context including long-term and recent memories.
        """
        parts = []
        
        # Long-term memory
        long_term = self.read_long_term()
        if long_term:
            parts.append("## Long-term Memory\n" + long_term)
        
        # Today's notes
        today = self.read_today()
        if today:
            parts.append("## Today's Notes\n" + today)
        
        return "\n\n".join(parts) if parts else ""

    # -------------------------------------------------------------------------
    # ADD Realm Tracking
    # -------------------------------------------------------------------------

    def log_realm(self, realm: str) -> None:
        """
        Log a realm detection to today's notes.

        Args:
            realm: The detected realm ('assess', 'decide', or 'do').
        """
        timestamp = datetime.now().strftime("%H:%M")
        realm_emoji = {"assess": "🔴", "decide": "🟠", "do": "🟢"}.get(realm.lower(), "⚪")
        entry = f"- {timestamp} {realm_emoji} {realm.upper()}"
        self.append_today(entry)

    def get_realm_summary(self) -> dict[str, int]:
        """
        Get a summary of realm activity for today.

        Returns:
            Dict with realm counts: {'assess': N, 'decide': N, 'do': N}
        """
        today_content = self.read_today()
        counts = Counter()

        # Match realm log entries: "- HH:MM 🔴 ASSESS" etc.
        pattern = r"- \d{2}:\d{2} [🔴🟠🟢⚪] (ASSESS|DECIDE|DO)"
        matches = re.findall(pattern, today_content)

        for realm in matches:
            counts[realm.lower()] += 1

        return dict(counts)

    def get_realm_flow_summary(self) -> str:
        """
        Get a formatted realm flow summary for today.

        Returns:
            Formatted string like "Realm Flow: 60% Assess, 30% Do, 10% Decide"
        """
        counts = self.get_realm_summary()
        total = sum(counts.values())

        if total == 0:
            return "No realm activity recorded today."

        percentages = []
        for realm in ["assess", "decide", "do"]:
            count = counts.get(realm, 0)
            pct = round(100 * count / total)
            if pct > 0:
                emoji = {"assess": "🔴", "decide": "🟠", "do": "🟢"}[realm]
                percentages.append(f"{pct}% {emoji} {realm.capitalize()}")

        return "Realm Flow: " + ", ".join(percentages)

    def append_realm_summary_to_today(self) -> None:
        """Append a realm flow summary section to today's notes."""
        summary = self.get_realm_flow_summary()
        if "No realm activity" not in summary:
            self.append_today(f"\n## {summary}\n")
