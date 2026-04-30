# AIGernon Module Marketplace — Full Implementation Plan

> **Branch note:** Implementation will be done on a separate branch `feat/marketplace`, until completion. Do not merge to `main` without explicit approval.

---

## Architecture decisions (locked in before writing a line of code)

1. **Module code ships in the monorepo for builtin modules.** External community modules are cloned into `aigernon/modules/external/` at runtime.
2. **Activation is per-instance via DB.** Install = DB record + workspace setup. No restarts required for activation/deactivation.
3. **All FastAPI routers are mounted at startup** (both builtin and previously-installed external). New external installs require a reload of the router, handled by a controlled app restart or router hot-swap.
4. **Frontend module pages are statically compiled** for builtin modules. External modules get a generic data view rendered from their API responses. True custom UI for external modules is Phase 2 (pre-compiled React bundles).
5. **x402 signing happens in the frontend.** The browser wallet signs the transaction; the backend only relays.
6. **Registry is a separate GitHub repo** with a Cloudflare Worker API. It is not part of this codebase but is documented fully below.

---

## Step 1 — Module specification + CLI scaffolder

### 1.1 manifest.json schema

Every module (builtin or external) must have a `manifest.json` at its root.

```json
{
  "id": "coaching",
  "name": "Coaching",
  "slug": "coaching",
  "description": "Structured reflection and growth sessions using the ADD framework.",
  "long_description": "Optional multi-line markdown for the marketplace detail page.",
  "version": "1.0.0",
  "author": "dragosroua",
  "author_url": "https://github.com/dragosroua",
  "homepage": "https://github.com/dragosroua/aigernon-coaching",
  "icon": "brain",
  "screenshots": [],
  "tags": ["mindset", "productivity"],
  "aigernon_min_version": "2.0.0",
  "license": "MIT",
  "price": null,
  "surfaces": ["ui", "agent", "api"],
  "nav": {
    "label": "Coaching",
    "icon": "brain",
    "href": "/coaching",
    "order": 30
  },
  "permissions": ["workspace_read", "workspace_write", "db_read", "db_write"],
  "dependencies": [],
  "config_schema": {}
}
```

**Field rules:**
- `id` — lowercase, hyphens only, globally unique
- `surfaces` — array subset of `["ui", "agent", "api"]`; must have at least one
- `price` — `null` for free, or `{"amount": "1.00", "currency": "USDC", "network": "base", "payee": "0x..."}`
- `permissions` — declare what the module touches; enforced by the loader
- `config_schema` — JSON Schema for user-configurable settings; empty `{}` means no config
- `nav` — required if `"ui"` in surfaces; `order` determines sidebar position (Projects=10, Cron=20, etc.)

### 1.2 Module directory structure

**Builtin (in this repo):**
```
aigernon/modules/
  __init__.py
  base.py
  loader.py
  registry.py
  validator.py
  builtin/
    __init__.py
    projects/
      __init__.py
      manifest.json
      routes.py          ← FastAPI APIRouter
      tools.py           ← list of Tool subclasses
      SKILL.md
      setup.py           ← async setup(instance_id, workspace, db) function
      schema.sql         ← optional, module-specific DB tables
    cron/
      __init__.py
      manifest.json
      routes.py
      tools.py
      SKILL.md
      setup.py
      schema.sql
    coaching/
      __init__.py
      manifest.json
      routes.py
      tools.py
      SKILL.md
      setup.py
      schema.sql
  external/
    .gitkeep
```

**External module (community repo, cloned here at runtime):**
```
aigernon/modules/external/finance/   ← cloned from git
  manifest.json
  __init__.py
  routes.py
  tools.py
  SKILL.md
  setup.py
  schema.sql
  README.md
```

**Web (frontend, all statically compiled):**
```
web/src/modules/
  index.ts               ← MODULE_REGISTRY map (id → component imports)
  projects/
    page.tsx
    nav.ts
  cron/
    page.tsx
    nav.ts
  coaching/
    page.tsx
    nav.ts
```

### 1.3 Python base classes

**`aigernon/modules/base.py`**

```python
from abc import ABC, abstractmethod
from pathlib import Path
from fastapi import APIRouter

class ModuleManifest:
    id: str
    name: str
    slug: str
    version: str
    author: str
    icon: str
    tags: list[str]
    aigernon_min_version: str
    price: dict | None
    surfaces: list[str]
    nav: dict | None
    permissions: list[str]
    dependencies: list[str]
    config_schema: dict
    source: str        # "builtin" | git URL
    source_path: Path  # absolute path to module directory

class LoadedModule:
    manifest: ModuleManifest
    router: APIRouter | None   # None if no "api" surface
    tools: list               # empty if no "agent" surface
    skill_content: str        # SKILL.md content, empty string if absent
    setup_fn: callable | None # async setup(instance_id, workspace, db)
    schema_sql: str | None    # contents of schema.sql if present
```

### 1.4 ModuleLoader

**`aigernon/modules/loader.py`**

```python
class ModuleLoader:
    """
    Discovers, validates, loads, and manages modules.

    Builtin modules:   aigernon/modules/builtin/{id}/
    External modules:  aigernon/modules/external/{id}/
    """

    def __init__(self, workspace: Path, db: "Database"):
        self.workspace = workspace
        self.db = db
        self._loaded: dict[str, LoadedModule] = {}
        self._builtin_dir = Path(__file__).parent / "builtin"
        self._external_dir = Path(__file__).parent / "external"

    # Discovery
    def discover_all(self) -> list[ModuleManifest]:
        """Return manifests for all builtin + installed external modules."""

    def discover_builtin(self) -> list[ModuleManifest]:
        """Scan builtin/ directory for manifest.json files."""

    def discover_external(self) -> list[ModuleManifest]:
        """Scan external/ directory for manifest.json files."""

    # Loading
    def load_all(self) -> None:
        """Load all discovered modules into _loaded dict."""

    def load(self, module_id: str) -> LoadedModule:
        """
        Import a module's Python code.
        - Import routes.py → extract 'router' APIRouter
        - Import tools.py → extract 'tools' list
        - Read SKILL.md
        - Import setup.py → extract 'setup' async function
        - Read schema.sql
        """

    def get(self, module_id: str) -> LoadedModule | None:
        return self._loaded.get(module_id)

    def get_all_routers(self) -> list[tuple[str, APIRouter]]:
        """Return (prefix, router) pairs for all loaded modules."""

    def get_tools_for_instance(self, active_module_ids: list[str]) -> list:
        """Return combined tool list for all active modules."""

    def get_skills_for_instance(self, active_module_ids: list[str]) -> str:
        """Return combined SKILL.md content for active modules."""

    # Installation
    async def install_from_git(self, repo_url: str, instance_id: str) -> ModuleManifest:
        """
        1. git clone repo_url into external/{derived_id}/
        2. validate_manifest()
        3. check version compatibility
        4. run schema.sql if present
        5. run setup(instance_id, workspace, db)
        6. load into _loaded
        7. hot-mount router onto app (if possible)
        Returns manifest.
        """

    async def enable_for_instance(self, module_id: str, instance_id: str, license_token: str | None = None):
        """
        For builtin modules or already-installed external modules.
        1. Validate module is loaded
        2. Run setup() for this instance
        3. Write instance_modules row
        """

    async def disable_for_instance(self, module_id: str, instance_id: str):
        """
        1. Remove instance_modules row
        2. Archive instance data (move workspace folder to .archived/)
        """

    # Validation
    def validate_manifest(self, path: Path) -> ModuleManifest:
        """Parse and validate manifest.json. Raises on invalid."""

    def check_version_compat(self, manifest: ModuleManifest) -> bool:
        """Compare aigernon_min_version against current version."""

    def check_permissions(self, manifest: ModuleManifest) -> list[str]:
        """Return list of permission warnings for display in UI."""
```

### 1.5 ModuleValidator

**`aigernon/modules/validator.py`**

```python
class ModuleValidator:
    """
    Security and compatibility checks for external modules.
    Run before installing any external module.
    """

    BANNED_IMPORTS = ["subprocess", "os.system", "eval", "exec", "__import__"]
    REQUIRED_FILES = ["manifest.json", "__init__.py"]
    OPTIONAL_FILES = ["routes.py", "tools.py", "SKILL.md", "setup.py", "schema.sql"]

    def validate(self, module_path: Path) -> ValidationResult:
        """
        Run all checks. Returns ValidationResult with passed/warnings/errors.

        Checks:
        1. Required files present
        2. manifest.json parses correctly against schema
        3. routes.py exports 'router' (APIRouter instance)
        4. tools.py exports 'tools' (list of Tool subclasses)
        5. setup.py exports 'setup' (async callable)
        6. schema.sql contains only CREATE TABLE / CREATE INDEX (no DROP, no ALTER)
        7. No banned imports in any .py file
        8. No absolute paths outside workspace
        9. Declared permissions match actual code usage
        """

    def _scan_imports(self, py_file: Path) -> list[str]:
        """AST-parse Python file, extract all imports."""

    def _check_sql_safety(self, sql: str) -> list[str]:
        """Return list of dangerous SQL statements found."""

class ValidationResult:
    passed: bool
    warnings: list[str]
    errors: list[str]
```

### 1.6 Database schema additions

New tables added in a migration (version-gated in `database.py`):

```sql
-- All modules known to this aigernon instance
-- (builtin always present; external added on install)
CREATE TABLE IF NOT EXISTS modules (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  version       TEXT NOT NULL,
  source        TEXT NOT NULL,        -- "builtin" | git URL
  source_path   TEXT NOT NULL,        -- absolute path
  manifest_json TEXT NOT NULL,        -- full manifest as JSON string
  installed_at  TEXT NOT NULL,
  status        TEXT DEFAULT 'active' -- 'active' | 'error' | 'disabled'
);

-- Per-instance module activation
CREATE TABLE IF NOT EXISTS instance_modules (
  instance_id   TEXT NOT NULL,
  module_id     TEXT NOT NULL,
  enabled_at    TEXT NOT NULL,
  config_json   TEXT DEFAULT '{}',
  license_token TEXT,                 -- signed JWT for paid modules
  PRIMARY KEY (instance_id, module_id),
  FOREIGN KEY (instance_id) REFERENCES instances(id),
  FOREIGN KEY (module_id)   REFERENCES modules(id)
);

-- Local usage events (for per-instance stats)
CREATE TABLE IF NOT EXISTS module_events (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  module_id   TEXT NOT NULL,
  instance_id TEXT,
  event_type  TEXT NOT NULL,  -- 'install','uninstall','tool_call','page_view','error'
  event_data  TEXT DEFAULT '{}',
  ts          TEXT NOT NULL
);
```

New `Database` methods:
```python
async def get_active_modules(self, instance_id: str) -> list[str]
async def is_module_active(self, instance_id: str, module_id: str) -> bool
async def enable_module(self, instance_id: str, module_id: str, config: dict, license_token: str | None)
async def disable_module(self, instance_id: str, module_id: str)
async def get_all_modules(self) -> list[dict]
async def upsert_module(self, manifest: ModuleManifest)
async def log_module_event(self, module_id: str, instance_id: str, event_type: str, data: dict)
async def get_module_stats(self, module_id: str, instance_id: str, days: int) -> dict
```

### 1.7 App startup integration

**`aigernon/api/app.py`** additions:

```python
# Initialize module loader (global singleton)
module_loader = ModuleLoader(workspace=get_data_dir(), db=db)
module_loader.load_all()

# Mount all module routers
for module_id, router in module_loader.get_all_routers():
    app.include_router(router, prefix=f"/{module_id}", tags=[module_id])

# Expose loader via app state
app.state.module_loader = module_loader
```

Module route guard dependency (added to every module router):
```python
async def require_module_active(
    request: Request,
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
) -> None:
    module_id = request.url.path.split("/")[1]
    instance_id = user.get("active_instance_id")
    if not await db.is_module_active(instance_id, module_id):
        raise HTTPException(status_code=404, detail=f"Module '{module_id}' not installed")
```

### 1.8 Agent integration

**`aigernon/agent/loop.py`** — `AgentLoop.__init__` adds:
```python
self.module_loader = module_loader  # injected from pool
```

Per-request tool registration in `process_direct`:
```python
active_ids = await self.db.get_active_modules(instance_id)
module_tools = self.module_loader.get_tools_for_instance(active_ids)
for tool in module_tools:
    self.tools.register(tool)
```

**`aigernon/agent/context.py`** — `build_system_prompt` adds:
```python
module_skills = self.module_loader.get_skills_for_instance(active_module_ids)
if module_skills:
    parts.append(f"# Installed Module Skills\n\n{module_skills}")
```

### 1.9 CLI scaffolder

New command group `aigernon module`:

```bash
aigernon module create <name>       # scaffold new module directory
aigernon module install <path|url>  # install from local path or git URL
aigernon module list                # list installed modules
aigernon module uninstall <id>      # uninstall a module
aigernon module validate <path>     # run validator without installing
```

`aigernon module create coaching` generates:
```
aigernon-coaching/
  manifest.json          ← scaffolded with placeholders
  __init__.py
  routes.py              ← example router with one GET endpoint
  tools.py               ← example Tool subclass
  SKILL.md               ← template with instructions
  setup.py               ← empty async setup() function
  schema.sql             ← commented example CREATE TABLE
  README.md
  .gitignore
```

---

## Step 2 — Refactoring existing features as builtin modules

### 2.1 Projects module

Move existing projects code into module structure. No behavior changes.

**Files to create:**
- `aigernon/modules/builtin/projects/manifest.json`
- `aigernon/modules/builtin/projects/routes.py` ← from `aigernon/api/routes/projects.py`
- `aigernon/modules/builtin/projects/tools.py` ← new: project CRUD tools for agent
- `aigernon/modules/builtin/projects/SKILL.md` ← move + expand existing
- `aigernon/modules/builtin/projects/setup.py` ← create workspace `projects/` folder
- `aigernon/modules/builtin/projects/schema.sql` ← no new tables (uses existing)

**Files to modify:**
- `aigernon/api/app.py` ← remove direct projects router include (now via module loader)
- `aigernon/api/routes/projects.py` ← kept as thin shim importing from module

**Backwards compat:** existing `/projects/...` URLs unchanged.

### 2.2 Cron module

Same pattern as Projects.

**Files to create:**
- `aigernon/modules/builtin/cron/manifest.json`
- `aigernon/modules/builtin/cron/routes.py`
- `aigernon/modules/builtin/cron/tools.py`
- `aigernon/modules/builtin/cron/SKILL.md`
- `aigernon/modules/builtin/cron/setup.py`

### 2.3 Coaching module (new, first net-new builtin)

**manifest.json:**
```json
{
  "id": "coaching",
  "name": "Coaching",
  "slug": "coaching",
  "description": "Structured coaching sessions and insight tracking using the ADD framework.",
  "version": "1.0.0",
  "icon": "brain",
  "tags": ["mindset", "productivity", "reflection"],
  "surfaces": ["ui", "agent", "api"],
  "nav": {"label": "Coaching", "icon": "brain", "href": "/coaching", "order": 30},
  "permissions": ["workspace_read", "workspace_write", "db_read", "db_write"]
}
```

**schema.sql:**
```sql
CREATE TABLE IF NOT EXISTS coaching_sessions (
  id          TEXT PRIMARY KEY,
  instance_id TEXT NOT NULL,
  topic       TEXT NOT NULL,
  realm       TEXT,               -- assess | decide | do
  started_at  TEXT NOT NULL,
  ended_at    TEXT,
  status      TEXT DEFAULT 'active'  -- active | completed | archived
);

CREATE TABLE IF NOT EXISTS coaching_insights (
  id          TEXT PRIMARY KEY,
  session_id  TEXT NOT NULL,
  instance_id TEXT NOT NULL,
  content     TEXT NOT NULL,
  tags        TEXT DEFAULT '[]',
  created_at  TEXT NOT NULL,
  FOREIGN KEY (session_id) REFERENCES coaching_sessions(id)
);
```

**routes.py endpoints:**
```
GET  /coaching/sessions
POST /coaching/sessions
GET  /coaching/sessions/{id}
PATCH /coaching/sessions/{id}
GET  /coaching/sessions/{id}/insights
POST /coaching/sessions/{id}/insights
GET  /coaching/insights
GET  /coaching/insights/search?q=
```

**tools.py agent tools:**
```python
class CreateCoachingSessionTool(Tool):
    name = "create_coaching_session"
    # params: topic (str), realm (str optional)

class LogInsightTool(Tool):
    name = "log_insight"
    # params: session_id (str), content (str), tags (list optional)

class GetCoachingHistoryTool(Tool):
    name = "get_coaching_history"
    # params: limit (int, default 5)

class SearchInsightsTool(Tool):
    name = "search_insights"
    # params: query (str)
```

**SKILL.md:** Teaches the agent how to run a coaching session using the ADD framework — when to create sessions, how to guide reflection, how to surface past insights.

**Frontend page.tsx:** Sessions list, session detail with insights timeline, search.

---

## Step 3 — Marketplace API endpoints

All under `aigernon/api/routes/marketplace.py`, registered at `/marketplace`.

### 3.1 Endpoint definitions

```
GET  /marketplace
     Query: tag (str), price (free|paid|all), status (installed|available|all)
     Response: { modules: MarketplaceModule[] }

GET  /marketplace/active
     Response: { module_ids: string[] }
     Used by sidebar on every app load.

GET  /marketplace/{id}
     Response: full MarketplaceModule + long_description + skill_preview

POST /marketplace/{id}/install
     Body: { repo_url?: string, config?: object }
     Free module  → install directly, return { installed: true }
     Paid module  → return { requires_payment: true, payment_info: X402PaymentInfo }

POST /marketplace/{id}/install/confirm-payment
     Body: { transaction_hash: string, signed_authorization: string }
     Completes install after payment verification.

DELETE /marketplace/{id}
     Disables for current instance. Archives data.
     Response: { uninstalled: true }

GET  /marketplace/{id}/stats
     Response: local module stats (tool calls, page views, errors, by day for last 30d)

POST /marketplace/refresh
     Admin only. Triggers refresh of registry cache from remote.
```

**MarketplaceModule response shape:**
```json
{
  "id": "coaching",
  "name": "Coaching",
  "slug": "coaching",
  "description": "...",
  "version": "1.0.0",
  "author": "dragosroua",
  "icon": "brain",
  "tags": ["mindset"],
  "price": null,
  "surfaces": ["ui", "agent", "api"],
  "nav": { "label": "Coaching", "icon": "brain", "href": "/coaching", "order": 30 },
  "status": "installed",
  "installed_at": "2026-04-01T09:00:00Z",
  "install_count": 142,
  "local_stats": {
    "last_used": "2026-04-15T10:22:00Z",
    "total_tool_calls": 89
  }
}
```

### 3.2 Registry cache

Fetched from `https://registry.aigernon.io/modules` at startup and every hour.
Cached in memory + `workspace/registry_cache.json` as offline fallback.
Merged with local discovery (builtin modules always appear even if absent from remote registry).

### 3.3 Module status computation

```python
def compute_module_status(manifest, active_ids, current_version) -> str:
    if not check_version_compat(manifest, current_version):
        return "incompatible"
    if manifest.id in active_ids:
        return "installed"
    return "available"
```

---

## Step 4 — Frontend marketplace UI

### 4.1 New files

```
web/src/
  app/(app)/marketplace/
    page.tsx
    [id]/page.tsx
  stores/
    marketplace-store.ts
  components/marketplace/
    module-card.tsx
    module-grid.tsx
    module-filters.tsx
    module-detail.tsx
    install-button.tsx
    price-badge.tsx
    stats-chart.tsx
  modules/
    index.ts
    projects/page.tsx   ← moved
    projects/nav.ts
    cron/page.tsx       ← moved
    cron/nav.ts
    coaching/page.tsx   ← new
    coaching/nav.ts
```

### 4.2 marketplace-store.ts

```typescript
interface MarketplaceModule {
  id: string
  name: string
  slug: string
  description: string
  version: string
  author: string
  icon: string
  tags: string[]
  price: { amount: string; currency: string } | null
  surfaces: string[]
  nav: { label: string; icon: string; href: string; order: number } | null
  status: "installed" | "available" | "incompatible"
  installed_at: string | null
  install_count: number
  local_stats: { last_used: string | null; total_tool_calls: number }
}

interface MarketplaceStore {
  modules: MarketplaceModule[]
  activeIds: string[]
  isLoading: boolean
  error: string | null

  fetchModules: () => Promise<void>
  fetchActive: () => Promise<void>
  install: (id: string) => Promise<InstallResult>
  uninstall: (id: string) => Promise<void>
  confirmPayment: (id: string, paymentResponse: PaymentResponse) => Promise<void>
}

type InstallResult =
  | { success: true }
  | { requires_payment: true; payment_info: X402PaymentInfo }
```

### 4.3 Dynamic sidebar

**`web/src/components/layout/sidebar.tsx`** modified to:
1. Import `useMarketplaceStore`
2. On mount, call `fetchActive()`
3. Build nav items from `MODULE_REGISTRY` filtered by `activeIds`, sorted by `order`
4. Refresh nav immediately on install/uninstall

```typescript
// web/src/modules/index.ts
export const MODULE_REGISTRY: Record<string, ModuleRegistryEntry> = {
  projects: {
    nav: { label: "Projects", icon: "folder", href: "/projects", order: 10 },
    Page: lazy(() => import("./projects/page")),
  },
  cron: {
    nav: { label: "Cron", icon: "clock", href: "/cron", order: 20 },
    Page: lazy(() => import("./cron/page")),
  },
  coaching: {
    nav: { label: "Coaching", icon: "brain", href: "/coaching", order: 30 },
    Page: lazy(() => import("./coaching/page")),
  },
}
```

### 4.4 Dynamic routing

**`web/src/app/(app)/[module]/page.tsx`** — catch-all:
```typescript
export default function ModulePage({ params }: { params: { module: string } }) {
  const entry = MODULE_REGISTRY[params.module]
  const { activeIds } = useMarketplaceStore()

  if (!entry) return <NotFound />
  if (!activeIds.includes(params.module)) return <ModuleNotInstalled id={params.module} />

  const { Page } = entry
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Page />
    </Suspense>
  )
}
```

### 4.5 Marketplace page layout

```
┌─────────────────────────────────────────────────────┐
│  Marketplace                        [Refresh]        │
├─────────────────────────────────────────────────────┤
│  [All] [Free] [Paid]   Tags: [mindset] [tracking]   │
├─────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │ 🧠 Coaching  │  │ 📊 Finance   │  │ 📖 Journal│ │
│  │ Installed ✓  │  │ Free         │  │ $1.00 USDC│ │
│  │ [Uninstall]  │  │ [Install]    │  │ [Buy]     │ │
│  └──────────────┘  └──────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────┘
```

**ModuleCard:** icon, name, description (2-line truncated), tags (up to 3), price badge, install count, action button.

**ModuleDetail:** full description, screenshots carousel, SKILL.md preview (what the agent gains), permissions list with explanations, version, author, stats chart if installed.

### 4.6 Install flow UI states

```
[Install] → loading → success → [Uninstall]
         → payment required → wallet prompt → signing → retry → success
         → error → [Retry]
```

---

## Step 5 — Observability

### 5.1 Local module event logging

| Event | Logged by | Data |
|-------|-----------|------|
| `install` | marketplace route | `{ version }` |
| `uninstall` | marketplace route | `{ had_data: bool }` |
| `tool_call` | BaseModuleTool.execute | `{ tool_name, success, duration_ms }` |
| `page_view` | frontend → POST /marketplace/{id}/events | `{}` |
| `error` | BaseModuleTool.execute on exception | `{ tool_name, error_type }` |

**BaseModuleTool** wraps every module tool's execute() to auto-log:
```python
class BaseModuleTool(Tool):
    module_id: str   # set by module loader on registration

    async def execute(self, **kwargs) -> str:
        t0 = time.monotonic()
        try:
            result = await self._execute(**kwargs)
            await self.db.log_module_event(
                module_id=self.module_id,
                instance_id=self._instance_id,
                event_type="tool_call",
                data={"tool": self.name, "success": True,
                      "duration_ms": int((time.monotonic()-t0)*1000)}
            )
            return result
        except Exception as e:
            await self.db.log_module_event(
                module_id=self.module_id, instance_id=self._instance_id,
                event_type="error",
                data={"tool": self.name, "error_type": type(e).__name__}
            )
            raise
```

### 5.2 Stats API response shape

```json
GET /marketplace/coaching/stats?period=30d

{
  "module_id": "coaching",
  "period": "30d",
  "tool_calls": {
    "total": 142,
    "by_tool": {
      "create_coaching_session": 12,
      "log_insight": 89,
      "get_coaching_history": 34,
      "search_insights": 7
    },
    "by_day": [
      {"date": "2026-04-01", "count": 5}
    ]
  },
  "page_views": { "total": 28, "by_day": [] },
  "errors": { "total": 0, "by_type": {} },
  "last_used": "2026-04-15T10:22:00Z",
  "installed_at": "2026-03-01T09:00:00Z"
}
```

### 5.3 Stats UI (installed module detail page)

"Usage" tab shows:
- Stacked bar chart: tool calls by tool per day (last 30d)
- Page views line chart
- Error rate indicator
- "Last used" timestamp

Library: `recharts`

### 5.4 Registry telemetry (opt-in, default off)

Setting: **Settings → Privacy → "Share anonymous module usage"**

When enabled, a daily background task runs:
```python
async def send_telemetry():
    """
    Aggregate local module_events from last 24h.
    Strip all instance/user identifiers.
    POST to https://registry.aigernon.io/telemetry

    Payload:
    {
      "aigernon_version": "2.1.0",
      "events": [
        {"module_id": "coaching", "event_type": "tool_call", "count": 15},
        {"module_id": "coaching", "event_type": "page_view", "count": 4}
      ]
    }
    No timestamps, no instance IDs, no user IDs.
    """
```

---

## Step 6 — x402 payment integration

### 6.1 Protocol overview

x402 is HTTP 402 Payment Required implemented as a micropayment standard.
Reference: [github.com/coinbase/x402](https://github.com/coinbase/x402)

**Network:** Base (Ethereum L2, fast, ~$0.001 gas)
**Asset:** USDC (ERC-20, 6 decimals — `1000000` units = $1.00)

### 6.2 Backend x402 client

**`aigernon/marketplace/x402.py`**

```python
@dataclass
class X402PaymentInfo:
    scheme: str           # "exact"
    network: str          # "base"
    asset: str            # USDC contract address on Base
    max_amount: int       # in smallest unit (1000000 = $1.00 USDC)
    pay_to: str           # author's wallet address
    resource: str         # URL of resource being purchased
    description: str
    max_timeout_seconds: int

@dataclass
class X402PaymentResponse:
    transaction_hash: str
    signed_authorization: str   # EIP-3009 authorization

class X402Client:
    async def check_price(self, url: str) -> X402PaymentInfo | None:
        """Probe endpoint. Return payment info if 402, None if 200 (free)."""

    async def execute_with_payment(
        self,
        url: str,
        payment_response: X402PaymentResponse
    ) -> dict:
        """Retry request with signed payment proof. Returns license token."""

    def _parse_payment_header(self, header: str) -> X402PaymentInfo: ...
    def _encode_payment_response(self, pr: X402PaymentResponse) -> str: ...
```

### 6.3 Install flow with payment

**`POST /marketplace/{id}/install`:**
```python
async def install_module(id, user, db, loader):
    manifest = loader.get(id).manifest

    if manifest.price is None:
        await loader.enable_for_instance(id, instance_id)
        return {"installed": True}

    x402 = X402Client()
    registry_url = f"https://registry.aigernon.io/modules/{id}/purchase"
    payment_info = await x402.check_price(registry_url)

    if payment_info is None:
        # Registry says free now
        await loader.enable_for_instance(id, instance_id)
        return {"installed": True}

    return {
        "requires_payment": True,
        "payment_info": {
            "module_id": id,
            "amount": payment_info.max_amount,
            "currency": "USDC",
            "network": payment_info.network,
            "pay_to": payment_info.pay_to,
            "description": payment_info.description,
        }
    }
```

**`POST /marketplace/{id}/install/confirm-payment`:**
```python
async def confirm_payment(id, body, ...):
    x402 = X402Client()
    registry_url = f"https://registry.aigernon.io/modules/{id}/purchase"
    result = await x402.execute_with_payment(
        registry_url,
        X402PaymentResponse(
            transaction_hash=body.transaction_hash,
            signed_authorization=body.signed_authorization,
        )
    )
    license_token = result["license_token"]

    if not validate_license_token(license_token, id):
        raise HTTPException(400, "Invalid license token from registry")

    await loader.enable_for_instance(id, instance_id, license_token=license_token)
    return {"installed": True}
```

### 6.4 License token format and validation

Registry signs a JWT using Ed25519:

```json
{
  "sub": "coaching",
  "instance": null,
  "tx": "0x...",
  "type": "lifetime",
  "expires_at": null,
  "iat": 1744000000,
  "iss": "registry.aigernon.io"
}
```

**`aigernon/marketplace/license.py`**

```python
REGISTRY_PUBLIC_KEY = "ed25519_public_key_here"  # bundled with aigernon

def validate_license_token(token: str, module_id: str) -> bool:
    """Decode JWT, verify Ed25519 sig, check sub == module_id, not expired."""

def is_license_valid_for_instance(token: str, module_id: str) -> bool:
    """Called on every module load. Works offline."""
```

### 6.5 Frontend wallet integration

**`web/src/lib/x402.ts`**

```typescript
interface PaymentInfo {
  module_id: string
  amount: number        // USDC base units (1000000 = $1.00)
  currency: "USDC"
  network: "base"
  pay_to: string        // author wallet address
  description: string
}

interface PaymentResult {
  transaction_hash: string
  signed_authorization: string  // EIP-3009
}

// Signs payment using connected wallet — no gas required (EIP-3009 is off-chain signing)
async function signPayment(info: PaymentInfo): Promise<PaymentResult>
```

Wallet library: `wagmi` + `viem`

**Payment UI flow:**
```
[Buy — $1.00 USDC]
  ↓ click
[Connect Wallet]           ← if no wallet connected
  ↓ wallet connected
[Confirm: Pay $1.00 USDC to @author for Coaching module]
  ↓ user approves in wallet extension (signing only, no gas)
[Completing purchase...]   ← backend submits tx, Base confirms in ~2s
  ↓ confirmed
[Installed ✓]
```

### 6.6 Stripe fallback (no crypto wallet)

Marketplace detail page shows `[Pay with card →]` which opens Stripe checkout.

Registry handles independently:
1. Stripe payment → webhook → registry issues license token
2. Registry emails "license claim URL" to user
3. User visits claim URL → token stored in `instance_modules.license_token`

No codebase changes needed beyond a "I have a license token" input in the install UI.

### 6.7 Registry server (external — separate deployment)

**Stack:** Cloudflare Worker + D1 (SQLite) + KV (cache)

**Endpoints:**
```
GET  /modules                  → index (GitHub-backed, KV-cached 1h)
GET  /modules/{id}             → single module detail
POST /modules/{id}/purchase    → returns 402 with X-Payment header
POST /modules/{id}/purchase    → with X-Payment-Response: validate, issue license JWT
GET  /modules/{id}/stats       → public aggregate stats
POST /telemetry                → receive anonymous usage events
GET  /dashboard/{id}           → author stats page (HTML)
```

**D1 schema:**
```sql
CREATE TABLE purchases (
  id            TEXT PRIMARY KEY,
  module_id     TEXT NOT NULL,
  tx_hash       TEXT NOT NULL UNIQUE,
  amount        INTEGER NOT NULL,
  currency      TEXT NOT NULL,
  network       TEXT NOT NULL,
  paid_to       TEXT NOT NULL,
  purchased_at  TEXT NOT NULL,
  license_token TEXT NOT NULL
);

CREATE TABLE module_stats (
  module_id   TEXT,
  date        TEXT,
  event_type  TEXT,
  count       INTEGER DEFAULT 0,
  PRIMARY KEY (module_id, date, event_type)
);
```

---

## Complete file change list

### New backend files
```
aigernon/modules/__init__.py
aigernon/modules/base.py
aigernon/modules/loader.py
aigernon/modules/registry.py
aigernon/modules/validator.py
aigernon/modules/builtin/__init__.py
aigernon/modules/builtin/projects/__init__.py
aigernon/modules/builtin/projects/manifest.json
aigernon/modules/builtin/projects/routes.py
aigernon/modules/builtin/projects/tools.py
aigernon/modules/builtin/projects/SKILL.md
aigernon/modules/builtin/projects/setup.py
aigernon/modules/builtin/projects/schema.sql
aigernon/modules/builtin/cron/__init__.py
aigernon/modules/builtin/cron/manifest.json
aigernon/modules/builtin/cron/routes.py
aigernon/modules/builtin/cron/tools.py
aigernon/modules/builtin/cron/SKILL.md
aigernon/modules/builtin/cron/setup.py
aigernon/modules/builtin/coaching/__init__.py
aigernon/modules/builtin/coaching/manifest.json
aigernon/modules/builtin/coaching/routes.py
aigernon/modules/builtin/coaching/tools.py
aigernon/modules/builtin/coaching/SKILL.md
aigernon/modules/builtin/coaching/setup.py
aigernon/modules/builtin/coaching/schema.sql
aigernon/modules/external/.gitkeep
aigernon/marketplace/__init__.py
aigernon/marketplace/x402.py
aigernon/marketplace/license.py
aigernon/api/routes/marketplace.py
aigernon/cli/module.py
```

### Modified backend files
```
aigernon/api/app.py           ← module loader init + router mounting
aigernon/api/db/database.py   ← module DB methods + migration
aigernon/agent/loop.py        ← inject module tools + skills
aigernon/agent/context.py     ← inject module skills into prompt
aigernon/agent/pool.py        ← pass module_loader to AgentLoop
aigernon/api/deps.py          ← expose module_loader dependency
```

### New frontend files
```
web/src/modules/index.ts
web/src/modules/projects/page.tsx        ← moved from (app)/projects/
web/src/modules/projects/nav.ts
web/src/modules/cron/page.tsx            ← moved from (app)/cron/
web/src/modules/cron/nav.ts
web/src/modules/coaching/page.tsx        ← new
web/src/modules/coaching/nav.ts
web/src/stores/marketplace-store.ts
web/src/components/marketplace/module-card.tsx
web/src/components/marketplace/module-grid.tsx
web/src/components/marketplace/module-filters.tsx
web/src/components/marketplace/module-detail.tsx
web/src/components/marketplace/install-button.tsx
web/src/components/marketplace/price-badge.tsx
web/src/components/marketplace/stats-chart.tsx
web/src/app/(app)/marketplace/page.tsx
web/src/app/(app)/marketplace/[id]/page.tsx
web/src/app/(app)/[module]/page.tsx      ← catch-all module route
web/src/lib/x402.ts
```

### Modified frontend files
```
web/src/components/layout/sidebar.tsx   ← dynamic nav from active modules
web/src/app/(app)/layout.tsx            ← remove hardcoded module nav items
web/src/app/(app)/projects/page.tsx     ← thin redirect or removed
web/src/app/(app)/cron/page.tsx         ← thin redirect or removed
web/package.json                         ← add wagmi, viem, recharts
```

---

## Implementation order

Steps must be done in this sequence to avoid breaking existing functionality:

| # | Task | Risk |
|---|------|------|
| 1 | DB migration — add 3 tables | None |
| 2 | ModuleLoader skeleton — discovery only, no routing changes | None |
| 3 | Refactor Projects as builtin module | Low — same URLs |
| 4 | Refactor Cron as builtin module | Low — same URLs |
| 5 | Module-aware routing — mount via loader instead of hardcoded | Medium |
| 6 | Marketplace API — free modules only | Low |
| 7 | Frontend marketplace page — install/uninstall builtins | Low |
| 8 | Dynamic sidebar — nav driven by active modules | Medium |
| 9 | Catch-all module routing `/[module]/page.tsx` | Medium |
| 10 | Coaching module — first net-new module end-to-end | Low |
| 11 | Observability — event logging + stats API + stats UI | Low |
| 12 | Registry telemetry — opt-in daily send | Low |
| 13 | x402 client — backend payment flow | Medium |
| 14 | Wallet integration — frontend signing (wagmi + viem) | Medium |
| 15 | Registry server — separate Cloudflare Worker deployment | External |

Steps 1–4 are pure refactoring with zero user-visible change.
Steps 5–10 deliver the core marketplace experience.
Steps 11–15 add the economic and analytics layer.
