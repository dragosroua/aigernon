---
name: projects
description: iOS app project management with ADD workflow - ideas, projects, tasks, versions
metadata: {"aigernon":{"emoji":"📱","always":false}}
---

# Projects Management

Manage iOS app development projects through the Assess → Decide → Do workflow.

## Core Concepts

### Ideas
Brainstorming playground. Ideas are always in **Assess** realm.
- Title + subitems
- Cannot be scheduled or executed
- Can be converted to a project when ready

### Projects
Full development efforts that flow through realms:
- **Assess**: Define scope, add/edit/remove tasks
- **Decide**: Lock scope, schedule tasks to versions
- **Do**: Execute tasks, capture results, mark done

### Tasks
Work items within a project:
- Types: `feature` or `bug`
- Flow: draft → ready → unscheduled → scheduled → in_progress → done

### Versions
Release milestones (e.g., 1.2.0):
- Branch: `version/X.x.x`
- Tasks are assigned to versions during Decide
- Released when all tasks are done

## Data Locations

```
~/.aigernon/workspace/
├── ideas/
│   └── {idea-id}.md
└── projects/
    └── {project-id}/
        ├── project.yaml
        ├── tasks/
        │   └── {task-id}.yaml
        ├── versions/
        │   └── {version}.yaml
        └── transitions.log
```

## Operations

### Ideas

**Create idea:**
```yaml
# Write to: ideas/{idea-id}.md
# {title}

- {item 1}
- {item 2}
```

**Add item to idea:**
Append `- {item}` to the idea file.

**Convert idea to project:**
1. Create project from idea title
2. Create draft tasks from items
3. Delete the idea file

### Projects

**Realm transitions:**

| From | To | Requirement |
|------|-----|-------------|
| Assess | Decide | All tasks must be `ready` |
| Decide | Do | All tasks must be `scheduled` |
| Do | Assess | Always allowed (logged) |
| Decide | Assess | Always allowed (logged) |

When moving Assess → Decide, all task statuses change from `ready` to `unscheduled`.

When moving Decide → Do, the scheduled version becomes `active`.

### Tasks

**In Assess realm:**
- Add tasks: status `draft`
- Edit task title/description
- Delete tasks
- Mark ready: draft → ready

**In Decide realm:**
- Schedule tasks: assign to version, status → `scheduled`
- Cannot add/edit/delete tasks

**In Do realm:**
- Start task: status → `in_progress`, generates branch name
- Block task: status → `blocked` with reason
- Complete task: status → `done`, stores execution log
- Cannot add/edit/delete tasks

### Versions

**Create version:**
```yaml
version: "1.2.0"
status: planned
branch: version/1.2.0
tasks: []
```

**Version status flow:**
- `planned` → `active` (when project enters Do)
- `active` → `ready` (when all tasks done)
- `ready` → `released` (after merge to main)

## Task Execution

When the user says "execute task X" or similar:

1. **Read task details**
   ```
   read_file ~/.aigernon/workspace/projects/{project}/tasks/{task_id}.yaml
   ```

2. **Read project config for repo**
   ```
   read_file ~/.aigernon/workspace/projects/{project}/project.yaml
   ```

3. **Implement the task**
   - Navigate to the repo directory
   - Create/checkout the task branch
   - Make code changes as needed
   - Run `xcodebuild` to verify compilation (if available)

4. **Store execution log**
   Update the task yaml with:
   ```yaml
   status: done
   execution_log: |
     {full log of what was done}
   completed_at: {timestamp}
   ```

5. **Report result**
   - Summarize what was done
   - Note: You do NOT commit code directly
   - User will review and commit

## Git Workflow

Branch naming:
- Features: `feat/{task-title-slug}`
- Bugs: `bug/{task-title-slug}`
- Versions: `version/X.x.x`

Flow:
1. Work on `feat/xxx` or `bug/xxx` branch
2. Merge into `version/X.x.x` when done
3. When all tasks done, `version/X.x.x` merges to `main`
4. XCode Cloud builds on merge to `main`

## Meta-cognition

Track realm dwell time for insights:
- `transitions.log` records all realm changes with timestamps
- Use to identify projects stuck too long in one realm
- Assess: defining too long → scope creep?
- Decide: scheduling too long → priority issues?
- Do: executing too long → blocked or complex?

## CLI Reference

```bash
# Ideas
aigernon ideas list
aigernon ideas add "Widget Redesign"
aigernon ideas show widget-redesign
aigernon ideas add-item widget-redesign "dark mode support"
aigernon ideas convert widget-redesign --repo git@github.com:user/app.git
aigernon ideas delete widget-redesign

# Projects
aigernon projects list [--realm assess|decide|do]
aigernon projects add "MyApp" --repo <url>
aigernon projects show myapp
aigernon projects move myapp decide
aigernon projects move myapp assess --reason "missing auth scope"
aigernon projects stuck [--days 7]

# Tasks
aigernon tasks list myapp [--status draft|ready|...]
aigernon tasks add myapp "Auth flow" --type feature
aigernon tasks show myapp 001
aigernon tasks ready myapp 001
aigernon tasks schedule myapp 001 --version 1.2.0
aigernon tasks start myapp 001 [--branch feat/auth]
aigernon tasks done myapp 001 [--log result.txt]

# Versions
aigernon versions list myapp
aigernon versions add myapp 1.2.0
aigernon versions show myapp 1.2.0
aigernon versions release myapp 1.2.0
aigernon versions mark-released myapp 1.2.0
```

## Integration with ADD Framework

Projects map naturally to ADD:

**Assess (red):** Ideas live here permanently. Projects start here. Explore scope, define tasks.

**Decide (yellow):** Commit to scope. Schedule tasks to versions. This is the "what will we ship" phase.

**Do (green):** Execute. Ship. Mark done. Move fast.

When reviewing projects, use realm time analysis to detect imbalance:
- Too much Assess = endless exploration
- Too much Decide = commitment avoidance
- Too much Do without completion = execution issues
