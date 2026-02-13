# Coaching Module

A between-session companion for coaches and their clients.

> "I won't coach you — I hold the space until we meet."

---

## Overview

The coaching module provides:

- **Idea capture** with ADD realm tagging
- **Question parking** for next session
- **Emergency support** with grounding + coach alerts
- **Session review** and history
- **Pre-session prep** summaries

It integrates with AIGernon's ADD framework while maintaining strict boundaries — it captures and holds, but does not coach.

---

## For Coaches

### Setup

#### Add a Client

```bash
aigernon coaching add-client \
  --id telegram:123456789 \
  --name "Client Name" \
  --coach-chat-id 987654321 \
  --timezone "Europe/Bucharest"
```

The client ID is their channel and chat ID (e.g., `telegram:123456789`).

#### List Clients

```bash
aigernon coaching list
```

#### Pre-Session Prep

Before each session, run:

```bash
aigernon coaching prep --client telegram:123456789
```

This shows:
- Ideas captured since last session (with realm tags)
- Questions parked for discussion
- Emergency flags (if any)
- Realm flow patterns

#### Add Session Notes

After a session:

```bash
aigernon coaching add-session \
  --client telegram:123456789 \
  --date 2024-02-10 \
  --file notes.md
```

Or interactively:

```bash
aigernon coaching add-session --client telegram:123456789
# Enter notes, Ctrl+D when done
```

#### View History

```bash
aigernon coaching history --client telegram:123456789 --days 30
```

---

## For Clients

Clients interact with AIGernon through natural conversation (typically via Telegram).

### Capture Ideas

**Triggers:**
- "I just realized..."
- "I had a thought about..."
- "Insight: ..."

**What happens:**
1. AIGernon detects the cognitive realm (Assess/Decide/Do)
2. Appends to the client's ideas file with timestamp and realm tag
3. Acknowledges briefly

**Example:**
```
Client: "I realized I've been using busyness as avoidance"
AIGernon: "Got it. Captured for your next session."
```

The idea is stored with its realm:
```markdown
## 2024-02-10 14:32 🔴 ASSESS

I've been using busyness as avoidance

---
```

### Park Questions

**Triggers:**
- "Question for [coach]"
- "Ask about..."
- "Next session I want to discuss..."

**Example:**
```
Client: "Question for Sarah: should I loop in HR before talking to my manager?"
AIGernon: "Question parked for your next session."
```

### Emergency Support

**Triggers:**
- "I'm spiraling"
- "Panicking"
- "Need help"
- Crisis language

**What happens:**
1. AIGernon offers grounding (if enabled):
   ```
   I'm here. Let's pause for a moment.

   Can you name:
   - 5 things you can see right now
   - 4 things you can physically feel
   - 3 things you can hear

   Take your time. I'm not going anywhere.
   ```

2. After grounding: "Would you like me to flag this for [coach]?"

3. If yes: logs the flag and sends alert to coach via Telegram

### Review Sessions

**Triggers:**
- "What did we cover last month?"
- "Last session..."
- "In January we discussed..."

AIGernon retrieves and summarizes relevant session history.

---

## Data Structure

```
~/.aigernon/workspace/coaching/
└── telegram_123456789/          # Client directory
    ├── client.yaml              # Configuration
    ├── ideas.md                 # Captured ideas (append-only)
    ├── questions.md             # Parked questions (append-only)
    ├── flags.md                 # Emergency flags (append-only)
    ├── history.md               # Coaching arc notes (coach maintains)
    └── sessions/
        ├── 2024-02-10.md        # Session notes
        └── 2024-02-24.md
```

### client.yaml

```yaml
client_id: "telegram:123456789"
name: "Client Name"
coach_chat_id: "987654321"
coach_channel: "telegram"
timezone: "Europe/Bucharest"
created_at: "2024-01-15T10:00:00Z"
preferences:
  grounding_enabled: true
  notification_threshold: "high"
```

### ideas.md

```markdown
# Ideas

## 2024-02-10 14:32 🔴 ASSESS

I've been using busyness as avoidance

---

## 2024-02-11 09:15 🟢 DO

Completed the difficult conversation with Sarah. Went better than expected.

---
```

### flags.md

```markdown
# Flags

## 2024-02-10 16:20 🚨 FLAGGED

Client message: "I'm panicking about tomorrow's meeting"
Grounding offered: Yes
Coach notified: Yes

---
```

---

## Realm Integration

Ideas are tagged with the detected ADD realm:

| Tag | Realm | Indicates |
|-----|-------|-----------|
| 🔴 | ASSESS | Exploratory thoughts, wondering, evaluating |
| 🟠 | DECIDE | Commitment-related, priorities, choices |
| 🟢 | DO | Execution observations, completions |

The prep command shows realm patterns:

```
Since last session (14 days):
- 23 interactions
- Realm flow: 68% Assess, 22% Do, 10% Decide
- Pattern: High assess with low decide may indicate stuck exploration
```

---

## Boundaries

The coaching module maintains strict boundaries:

**It DOES:**
- Acknowledge what clients share
- Capture ideas and questions accurately
- Offer grounding when appropriate
- Alert the coach when requested
- Review past sessions

**It does NOT:**
- Give advice
- Interpret experiences
- Suggest solutions
- Process emotions
- Engage in coaching conversations

**Deflection phrases used:**
- "That sounds important. Let's make sure [coach] knows about it."
- "I'll capture this for your next session."
- "This feels like something to explore with [coach]."

---

## CLI Reference

```bash
# List all clients
aigernon coaching list

# Add a new client
aigernon coaching add-client \
  --id telegram:123456789 \
  --name "Client Name" \
  --coach-chat-id 987654321 \
  [--coach-channel telegram] \
  [--timezone UTC]

# Add session notes
aigernon coaching add-session \
  --client telegram:123456789 \
  [--date 2024-02-10] \
  [--file notes.md]

# Pre-session preparation summary
aigernon coaching prep --client telegram:123456789

# View client history
aigernon coaching history \
  --client telegram:123456789 \
  [--days 30]
```

---

## Security Notes

- All coaching data is stored locally in `~/.aigernon/workspace/coaching/`
- No data leaves the system except coach notifications via Telegram
- Coach is responsible for backup and data retention
- Client identity is tied to their chat platform account
