# AIGernon

AIGernon is an always-on AI agent that understands *where you are* in your thinking process. Built on the Assess-Decide-Do (ADD) framework, it transforms collaboration from transactional to relational.

The name references *Flowers for Algernon* — but inverted. Algernon's intelligence was temporary. AIGernon embraces impermanence as a feature: each Assess→Decide→Do cycle is a small death and rebirth. Intelligence is cyclical, bound to context, which is by default changing.

<div align="center">
  <table>
    <tr>
      <td valign="middle" style="padding: 16px;">
        <img src="aigernon.png" alt="AIGernon" width="64" height="64">
      </td>
      <td valign="middle" style="padding: 16px;">
        <strong><em>A cognitive companion, not a task bot.</em></strong>
      </td>
    </tr>
  </table>
</div>

## The ADD Framework

Human cognition flows through three realms:

- **ASSESS** — Explore, evaluate, dream without commitment. No pressure to decide.
- **DECIDE** — Prioritize, allocate resources, commit. Brief and values-based.
- **DO** — Execute, complete, create livelines (not deadlines).

When the agent understands which realm you're in, it adapts:
- In Assess: expansive, curious, "what else?" not "what next?"
- In Decide: honors the weight of choosing, supports commitment
- In Do: clear, actionable, celebrates completions as new beginnings

**The cascade principle:** Poor Assess → Poor Decide → Poor Do. AIGernon watches for imbalances.

[Full framework documentation](https://github.com/dragosroua/claude-assess-decide-do-mega-prompt)

## Quick Start

### 1. Clone

```bash
git clone https://github.com/dragosroua/aigernon.git
cd aigernon
```

### 2. Install

```bash
pip install -e .
```

### 3. Configure

```bash
aigernon onboard
```

This creates `~/.aigernon/config.json`. Add your API key:

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

### 4. Chat

```bash
aigernon agent -m "I've been thinking about changing careers but I'm not sure"
```

AIGernon detects you're in Assess mode and responds expansively, without pushing you toward a decision.

### 5. Telegram (optional)

Add your Telegram bot token to the config:

```json
{
  "channels": {
    "telegram": {
      "token": "your-telegram-bot-token"
    }
  }
}
```

Then start:

```bash
aigernon channel telegram
```

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `model` | LLM model via OpenRouter | `anthropic/claude-sonnet-4-5` |
| `providers.openrouter.api_key` | Your OpenRouter API key | — |
| `channels.telegram.token` | Telegram bot token | — |
| `workspace` | Workspace directory | `~/.aigernon/workspace` |

## ADD Skills

AIGernon includes six cognitive skills:

| Skill | Description |
|-------|-------------|
| `add-core` | Core ADD framework (always loaded) |
| `add-realm-detection` | Language pattern detection (always loaded) |
| `add-assess` | Deep Assess realm support |
| `add-decide` | Deep Decide realm support |
| `add-do` | Deep Do realm support |
| `add-imbalance` | Stuck pattern detection |

## Realm-Aware Memory

AIGernon tracks your cognitive patterns:

- **Daily notes:** `~/.aigernon/workspace/memory/YYYY-MM-DD.md`
- **Long-term memory:** `~/.aigernon/workspace/memory/MEMORY.md`

Daily notes include realm flow logging:
```
- 09:15 ASSESS
- 09:32 DECIDE
- 10:45 DO

## Realm Flow: 40% Assess, 20% Decide, 40% Do
```

Over time, patterns emerge: "User tends to over-assess on financial decisions."

## Coaching Module

AIGernon includes a coaching assistant for between-session client support. It captures ideas, holds questions, handles emergencies, and reviews session history — without coaching.

> "I won't coach you — I hold the space until we meet."

### Setup

```bash
# Add a coaching client
aigernon coaching add-client \
  --id telegram:123456789 \
  --name "Client Name" \
  --coach-chat-id 987654321

# Add session notes after a session
aigernon coaching add-session \
  --client telegram:123456789 \
  --date 2024-02-10 \
  --file notes.md

# Pre-session prep (shows ideas, questions, flags since last session)
aigernon coaching prep --client telegram:123456789
```

### Client Operations

Clients interact via natural language through Telegram:

| Intent | Example | Action |
|--------|---------|--------|
| Capture idea | "I realized I've been avoiding conflict" | Appends to `ideas.md` with realm tag |
| Park question | "Ask coach about the HR situation" | Appends to `questions.md` |
| Emergency | "I'm spiraling, need help" | Grounding + optional coach alert |
| Review | "What did we cover last month?" | Summarizes session history |

### Data Structure

```
~/.aigernon/workspace/coaching/
└── telegram_123456789/
    ├── client.yaml      # Client config (name, coach contact)
    ├── ideas.md         # Captured ideas with realm tags
    ├── questions.md     # Questions for next session
    ├── flags.md         # Emergency flags
    ├── history.md       # Coaching arc notes
    └── sessions/
        └── 2024-02-10.md
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `aigernon coaching list` | List all clients |
| `aigernon coaching add-client` | Add a new client |
| `aigernon coaching add-session` | Add session notes |
| `aigernon coaching prep` | Pre-session summary |
| `aigernon coaching history` | View client history |

## Docker

```bash
docker build -t aigernon .
docker run -v ~/.aigernon:/root/.aigernon aigernon agent -m "Hello"
```

## Credits

- **ADD Framework:** Created by [Dragos Roua](https://dragosroua.com/assess-decide-do-framework/)
- **Base Agent Framework:** Forked from [nanobot](https://github.com/HKUDS/nanobot) by HKUDS
- **Name Inspiration:** *Flowers for Algernon* by Daniel Keyes

## More by the Author

- [addTaskManager](https://itunes.apple.com/app/apple-store/id1492487688?mt=8) — Native iOS/macOS ADD task manager
- [dragosroua.com](https://dragosroua.com)
- [ADD Framework Agnostic Skills](https://github.com/dragosroua/add-framework-skills)


## License

MIT
