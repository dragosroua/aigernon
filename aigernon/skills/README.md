# AIGernon Skills

This directory contains built-in skills that extend AIGernon's capabilities.

## Skill Format

Each skill is a directory containing a `SKILL.md` file with:
- YAML frontmatter (name, description, metadata)
- Markdown instructions for the agent

## ADD Framework Skills

The core cognitive layer of AIGernon. These skills implement the Assess-Decide-Do framework.

| Skill | Description |
|-------|-------------|
| `add-core` | Core ADD framework - always loaded |
| `add-realm-detection` | Realm detection patterns - always loaded |
| `add-assess` | Deep support for the Assess realm |
| `add-decide` | Deep support for the Decide realm |
| `add-do` | Deep support for the Do realm |
| `add-imbalance` | Detect and support stuck patterns |

## Coaching Skill

Between-session support for coaching clients.

| Skill | Description |
|-------|-------------|
| `coaching` | Captures ideas, holds questions, handles emergencies, reviews sessions |

The coaching skill integrates with the ADD framework to tag captured ideas with their detected realm (Assess/Decide/Do).

## Projects Skill

iOS app development workflow with ADD integration.

| Skill | Description |
|-------|-------------|
| `projects` | Manages ideas, projects, tasks, and versions through Assess→Decide→Do |

The projects skill enforces the ADD workflow:
- **Assess**: Define scope, add/edit tasks
- **Decide**: Lock scope, schedule tasks to versions
- **Do**: Execute tasks, capture results, ship

## Utility Skills

General-purpose capabilities inherited from nanobot.

| Skill | Description |
|-------|-------------|
| `github` | Interact with GitHub using the `gh` CLI |
| `weather` | Get weather info using wttr.in and Open-Meteo |
| `summarize` | Summarize URLs, files, and YouTube videos |
| `tmux` | Remote-control tmux sessions |
| `skill-creator` | Create new skills |
| `cron` | Schedule recurring tasks |

## Attribution

- ADD Framework skills created by Dragos Roua
- Utility skills adapted from [nanobot](https://github.com/HKUDS/nanobot)
- Skill format based on [OpenClaw](https://github.com/openclaw/openclaw) conventions
