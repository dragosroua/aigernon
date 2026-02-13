# Projects Module

iOS app development workflow using the ADD framework.

---

## Overview

The projects module manages iOS development through the Assess → Decide → Do workflow:

```
IDEAS (always Assess)
    │
    │ convert
    ▼
PROJECTS ─────────────────────────────────────────────
    │                                                  │
    │  ASSESS          DECIDE           DO            │
    │  ┌──────┐       ┌──────┐       ┌──────┐        │
    │  │ Add  │ ───►  │ Lock │ ───►  │ Run  │        │
    │  │ Edit │       │ Sched│       │ Ship │        │
    │  │ Tasks│       │ ule  │       │      │        │
    │  └──────┘       └──────┘       └──────┘        │
    │      ▲              │              │           │
    │      └──────────────┴──────────────┘           │
    │           (backtracking allowed)                │
    └─────────────────────────────────────────────────┘
```

---

## Core Concepts

### Ideas

Brainstorming playground. Ideas are **always in Assess** — they cannot be scheduled or executed.

- Simple title + bullet items
- Convert to project when ready to commit
- Deleted after conversion

### Projects

Full development efforts that flow through realms:

| Realm | Allowed Actions |
|-------|-----------------|
| **Assess** | Add tasks, edit tasks, delete tasks, mark ready |
| **Decide** | Schedule tasks to versions (no add/edit/delete) |
| **Do** | Execute tasks, mark done (no add/edit/delete) |

### Tasks

Work items within a project:

- **Types:** `feature` or `bug`
- **Status flow:** draft → ready → unscheduled → scheduled → in_progress → done

### Versions

Release milestones (e.g., `1.2.0`):

- Branch: `version/X.x.x`
- Tasks assigned during Decide
- Released when all tasks done

---

## Workflow

### 1. Create Ideas

```bash
aigernon ideas add "Widget Redesign"
aigernon ideas add-item widget-redesign "new grid layout"
aigernon ideas add-item widget-redesign "dark mode support"
aigernon ideas add-item widget-redesign "haptic feedback"
```

### 2. Convert to Project

When ready to commit:

```bash
aigernon ideas convert widget-redesign --repo git@github.com:user/myapp.git
```

This creates a project in **Assess** realm with draft tasks from the idea items.

### 3. Define Scope (Assess)

Add more tasks, edit existing ones, remove unnecessary ones:

```bash
aigernon tasks add myapp "Accessibility improvements" --type feature
aigernon tasks add myapp "Fix landscape layout" --type bug
```

Mark tasks as ready when definition is complete:

```bash
aigernon tasks ready myapp 001
aigernon tasks ready myapp 002
aigernon tasks ready myapp 003
```

### 4. Move to Decide

When all tasks are ready:

```bash
aigernon projects move myapp decide
```

Tasks become `unscheduled`, waiting for version assignment.

### 5. Schedule Tasks (Decide)

Create a version and assign tasks:

```bash
aigernon versions add myapp 1.2.0
aigernon tasks schedule myapp 001 --version 1.2.0
aigernon tasks schedule myapp 002 --version 1.2.0
aigernon tasks schedule myapp 003 --version 1.2.0
```

### 6. Move to Do

When all tasks are scheduled:

```bash
aigernon projects move myapp do
```

The version becomes `active`.

### 7. Execute Tasks (Do)

Start a task:

```bash
aigernon tasks start myapp 001
# Creates branch: feat/new-grid-layout
```

Execute via LLM or manually. When done:

```bash
aigernon tasks done myapp 001 --log execution.txt
```

### 8. Release Version

When all tasks are done:

```bash
aigernon versions release myapp 1.2.0
# Merge version/1.2.0 to main
# XCode Cloud builds on merge

aigernon versions mark-released myapp 1.2.0
```

---

## Git Workflow

The projects module follows a structured branching strategy:

```
main
  │
  └── version/1.2.0
        │
        ├── feat/new-grid-layout
        ├── feat/dark-mode-support
        ├── bug/landscape-layout
        │
        └── (merge all when done)
              │
              └── merge to main → XCode Cloud builds
```

**Branch naming:**
- Features: `feat/{task-title-slug}`
- Bugs: `bug/{task-title-slug}`
- Versions: `version/X.x.x`

---

## Backtracking

Movement between realms is **flexible** but logged:

```bash
# Discovered missing scope while in Do
aigernon projects move myapp assess --reason "missing auth tasks"
```

Transitions are recorded in `transitions.log`:

```
2024-02-10T10:00:00Z | created | assess
2024-02-12T14:30:00Z | assess -> decide | 2d 4h 30m in assess
2024-02-13T09:00:00Z | decide -> do | 18h 30m in decide
2024-02-14T11:00:00Z | do -> assess | scope gap discovered | 1d 2h in do
```

This enables meta-cognition: detecting projects that stay too long in one realm.

---

## Meta-Cognition

### Stuck Detection

Find projects stuck too long:

```bash
aigernon projects stuck --days 7
```

Output:
```
Projects Stuck > 7 Days
┌─────────────┬────────┬───────────────┐
│ Project     │ Realm  │ Time in Realm │
├─────────────┼────────┼───────────────┤
│ OldApp      │ Assess │ 14d 3h        │
│ StaleWidget │ Decide │ 9d 12h        │
└─────────────┴────────┴───────────────┘
```

### Realm Time Analysis

View time distribution:

```bash
aigernon projects show myapp
```

Output:
```
# MyApp
  Realm: Do
  Time: Assess: 5d 2h (45%) | Decide: 1d 8h (12%) | Do: 4d 6h (43%)
```

Patterns to watch:
- **High Assess %:** Possible scope creep or exploration paralysis
- **High Decide %:** Commitment issues or unclear priorities
- **High Do %:** Could be healthy, or perpetual doing without shipping

---

## Task Execution

When you ask AIGernon to execute a task:

1. **Reads task details** from the task YAML
2. **Reads project config** for repo location
3. **Implements the task** (code changes)
4. **Runs `xcodebuild`** to verify compilation (if available)
5. **Stores execution log** in the task file
6. **Reports result** (does NOT commit code)

You review the changes and commit manually.

---

## Data Structure

```
~/.aigernon/workspace/
├── ideas/
│   ├── widget-redesign.md
│   └── monetization-v2.md
└── projects/
    └── myapp/
        ├── project.yaml
        ├── transitions.log
        ├── tasks/
        │   ├── 001.yaml
        │   ├── 002.yaml
        │   └── 003.yaml
        └── versions/
            ├── 1_2_0.yaml
            └── 1_3_0.yaml
```

### project.yaml

```yaml
name: MyApp
repo: git@github.com:user/myapp.git
realm: do
current_version: "1.2.0"
created_at: "2024-02-10T10:00:00Z"
```

### tasks/001.yaml

```yaml
id: "001"
title: New grid layout
description: |
  Implement responsive grid for widgets
type: feature
status: in_progress
version: "1.2.0"
branch: feat/new-grid-layout
execution_log: null
created_at: "2024-02-10T10:30:00Z"
scheduled_at: "2024-02-12T14:30:00Z"
started_at: "2024-02-13T09:15:00Z"
completed_at: null
```

### versions/1_2_0.yaml

```yaml
version: "1.2.0"
status: active
branch: version/1.2.0
tasks: ["001", "002", "003"]
created_at: "2024-02-12T14:00:00Z"
released_at: null
```

---

## CLI Reference

### Ideas

```bash
aigernon ideas list                       # List all ideas
aigernon ideas add "Title"                # Create idea
aigernon ideas show <id>                  # Show idea details
aigernon ideas add-item <id> "item"       # Add item
aigernon ideas convert <id> --repo <url>  # Convert to project
aigernon ideas delete <id>                # Delete idea
```

### Projects

```bash
aigernon projects list [--realm assess|decide|do]
aigernon projects add "Name" --repo <url>
aigernon projects show <id>
aigernon projects move <id> <realm> [--reason "..."]
aigernon projects stuck [--days 7]
```

### Tasks

```bash
aigernon tasks list <project> [--status <status>] [--version <ver>]
aigernon tasks add <project> "Title" [--type feature|bug] [--desc "..."]
aigernon tasks show <project> <task>
aigernon tasks ready <project> <task>
aigernon tasks schedule <project> <task> --version <ver>
aigernon tasks start <project> <task> [--branch <name>]
aigernon tasks done <project> <task> [--log <file>]
```

### Versions

```bash
aigernon versions list <project>
aigernon versions add <project> <version>
aigernon versions show <project> <version>
aigernon versions release <project> <version>
aigernon versions mark-released <project> <version>
```

---

## ADD Integration

Projects map naturally to ADD realms:

| Realm | Project Phase | Activities |
|-------|---------------|------------|
| **Assess** | Discovery | Add tasks, explore scope, define requirements |
| **Decide** | Planning | Schedule tasks, assign versions, commit to scope |
| **Do** | Execution | Implement, test, ship |

The module enforces healthy transitions:
- Can't skip Assess (must define tasks)
- Can't skip Decide (must schedule to version)
- Can backtrack when needed (but it's logged)

This prevents:
- Shipping undefined work (skipping Assess)
- Endless planning without execution (stuck in Decide)
- Scope creep during execution (changes in Do)
