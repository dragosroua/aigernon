# AIGernon

**A cognitive companion that understands where you are in your thinking process.**

<div align="center">
  <img src="aigernon.png" alt="AIGernon" width="128" height="128">
  <br><br>
  <em>Not a task bot. A thinking partner.</em>
</div>

---

AIGernon is an always-on AI agent built on the **Assess-Decide-Do (ADD)** framework. It transforms AI collaboration from transactional ("do this task") to relational ("help me think through this").

The name references *Flowers for Algernon* — but inverted. Algernon's intelligence was temporary. AIGernon embraces impermanence as a feature: each Assess→Decide→Do cycle is a small death and rebirth. Intelligence is cyclical, bound to context.

## Core Philosophy: The ADD Framework

Human cognition flows through three realms:

| Realm | Mode | AIGernon's Response |
|-------|------|---------------------|
| **ASSESS** | Explore, evaluate, dream without commitment | Expansive. "What else?" not "what next?" |
| **DECIDE** | Prioritize, allocate resources, commit | Brief. Honors the weight of choosing. |
| **DO** | Execute, complete, ship | Clear, actionable. Celebrates completions. |

**The cascade principle:** Poor Assess leads to poor Decide leads to poor Do. AIGernon watches for this.

**Imbalance detection:**
- Stuck in Assess = analysis paralysis
- Stuck in Decide = commitment avoidance
- Stuck in Do = perpetual doing without reflection

[Full ADD Framework documentation →](docs/ADD_FRAMEWORK.md)

---

## Features

### Realm-Aware Conversation

AIGernon detects which cognitive realm you're in and adapts:

```
You: "I've been thinking about changing careers but I'm not sure"
AIGernon: [Detects ASSESS] "What aspects are you exploring?
          What would need to be true for this to feel right?"

You: "I've decided to apply for the senior role"
AIGernon: [Detects DECIDE] "Noted. What's your first step?"

You: "Working on the portfolio now, almost done with section 3"
AIGernon: [Detects DO] "Good momentum. Section 3 complete is a liveline."
```

### Cognitive Memory

AIGernon tracks your patterns over time:

- **Daily notes:** `~/.aigernon/workspace/memory/YYYY-MM-DD.md`
- **Long-term memory:** `~/.aigernon/workspace/memory/MEMORY.md`
- **Realm flow logging:** Tracks time spent in each realm

```
## Realm Flow: 40% Assess, 20% Decide, 40% Do
Pattern: User tends to over-assess on financial decisions.
```

### Coaching Module

A between-session companion for coaches and their clients.

> "I won't coach you — I hold the space until we meet."

- Captures client ideas with realm tags
- Parks questions for next session
- Handles emergencies with grounding + coach alerts
- Provides pre-session prep summaries

[Coaching documentation →](docs/COACHING.md)

### Projects Module

iOS app development management through the ADD workflow.

Ideas → Projects → Tasks → Versions → Release

- **Ideas** (always Assess): Brainstorming playground
- **Projects**: Flow through Assess → Decide → Do
- **Tasks**: Execute via LLM, capture results
- **Versions**: Track releases, manage branches

[Projects documentation →](docs/PROJECTS.md)

### Multi-Channel Support

- **CLI**: Direct terminal interaction
- **Telegram**: Always-on bot
- **Discord, WhatsApp, Feishu, DingTalk**: Additional channels

### Daemon Mode

Run AIGernon as a system service that survives reboots and auto-restarts on crash:

```bash
aigernon daemon install   # Install system service
aigernon daemon start     # Start the daemon
aigernon daemon status    # Check status
aigernon doctor           # Health check
```

Supports **macOS** (launchd) and **Linux** (systemd). [Daemon documentation →](docs/DAEMON.md)

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/dragosroua/aigernon.git
cd aigernon
pip install -e .
```

### 2. Configure

```bash
aigernon onboard
```

Edit `~/.aigernon/config.json`:

```json
{
  "providers": {
    "openrouter": {
      "api_key": "your-openrouter-key"
    }
  },
  "model": "anthropic/claude-sonnet-4-5"
}
```

### 3. Chat

```bash
aigernon agent -m "I've been thinking about restructuring the team"
```

### 4. Telegram (optional)

```json
{
  "channels": {
    "telegram": {
      "token": "your-telegram-bot-token"
    }
  }
}
```

```bash
aigernon channel telegram
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [ADD Framework](docs/ADD_FRAMEWORK.md) | Core cognitive framework |
| [Coaching Module](docs/COACHING.md) | Between-session client support |
| [Projects Module](docs/PROJECTS.md) | iOS development workflow |
| [Daemon & Service](docs/DAEMON.md) | Running as a system service |
| [Skills System](aigernon/skills/README.md) | Extensible capabilities |
| [Security](docs/SECURITY.md) | Security features and hardening |

---

## CLI Reference

### Core Commands

```bash
aigernon agent -m "message"     # One-shot conversation
aigernon agent                   # Interactive mode
aigernon channel telegram        # Start Telegram bot
aigernon onboard                 # Initial setup
aigernon config                  # Show configuration
```

### Coaching

```bash
aigernon coaching list                    # List clients
aigernon coaching add-client ...          # Add client
aigernon coaching prep --client ID        # Pre-session summary
aigernon coaching add-session ...         # Add session notes
```

### Projects

```bash
aigernon ideas list|add|show|convert      # Brainstorming
aigernon projects list|add|show|move      # Project management
aigernon tasks list|add|ready|schedule    # Task workflow
aigernon versions list|add|release        # Version control
```

### Daemon

```bash
aigernon daemon install       # Install system service
aigernon daemon uninstall     # Remove system service
aigernon daemon start         # Start the daemon
aigernon daemon stop          # Stop gracefully
aigernon daemon restart       # Restart the daemon
aigernon daemon status        # Show status (PID, uptime)
aigernon daemon logs          # Tail daemon logs
aigernon daemon logs -f       # Follow logs
aigernon doctor               # Health check
```

---

## Architecture

```
~/.aigernon/
├── config.json              # Configuration
├── daemon.pid               # Daemon process ID
├── daemon.status.json       # Daemon status (heartbeat, channels)
├── sessions/                # Conversation history
├── logs/
│   └── daemon.log           # Daemon output
└── workspace/
    ├── memory/              # Cognitive memory
    │   ├── MEMORY.md        # Long-term
    │   └── YYYY-MM-DD.md    # Daily notes
    ├── coaching/            # Coaching data
    │   └── {client_id}/
    ├── projects/            # Project data
    │   └── {project_id}/
    ├── ideas/               # Brainstorming
    ├── skills/              # Custom skills
    └── *.md                 # Bootstrap files
```

---

## Skills System

AIGernon loads cognitive skills dynamically:

| Skill | Always Loaded | Description |
|-------|---------------|-------------|
| `add-core` | Yes | Core ADD framework |
| `add-realm-detection` | Yes | Language pattern detection |
| `add-assess` | No | Deep Assess support |
| `add-decide` | No | Deep Decide support |
| `add-do` | No | Deep Do support |
| `add-imbalance` | No | Stuck pattern detection |
| `coaching` | No | Client support |
| `projects` | No | iOS development workflow |

Custom skills go in `~/.aigernon/workspace/skills/{name}/SKILL.md`.

---

## Security

AIGernon includes a security module to protect against abuse and unauthorized modifications:

| Feature | Description |
|---------|-------------|
| **Rate Limiting** | Per-user sliding window with burst protection |
| **Audit Logging** | Tool invocations, access denials, security events |
| **Integrity Monitoring** | SHA-256 hash verification for critical files |
| **Input Sanitization** | Protection against injection attacks |

```
~/.aigernon/
├── audit/                    # Daily audit logs (JSONL)
│   └── audit-YYYY-MM-DD.jsonl
└── security/
    └── integrity_hashes.json  # File integrity baselines
```

[Security documentation →](docs/SECURITY.md)

---

## Docker

```bash
docker build -t aigernon .
docker run -v ~/.aigernon:/root/.aigernon aigernon agent -m "Hello"
```

---

## Credits

- **ADD Framework:** [Dragos Roua](https://dragosroua.com/assess-decide-do-framework/)
- **Base Framework:** Forked from [nanobot](https://github.com/HKUDS/nanobot) by HKUDS
- **Name Inspiration:** *Flowers for Algernon* by Daniel Keyes

## Related Projects

- [addTaskManager](https://itunes.apple.com/app/apple-store/id1492487688?mt=8) — Native iOS/macOS ADD task manager
- [ADD Framework Skills](https://github.com/dragosroua/add-framework-skills) — Agnostic skill collection

## License

MIT
