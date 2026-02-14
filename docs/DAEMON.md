# Daemon & Service Management

AIGernon can run as a system service that starts automatically on login, restarts on crash, and can be managed via CLI commands.

## Quick Start

```bash
# Install the service
aigernon daemon install

# Start it
aigernon daemon start

# Check status
aigernon daemon status

# View logs
aigernon daemon logs -f
```

## Platform Support

| Platform | Service Manager | Service File Location |
|----------|-----------------|----------------------|
| macOS | launchd | `~/Library/LaunchAgents/com.aigernon.gateway.plist` |
| Linux | systemd (user) | `~/.config/systemd/user/aigernon.service` |
| Windows | Not supported | Use Docker or manual startup |

## Commands

### `aigernon daemon install`

Generates and installs the appropriate system service for your platform.

**macOS:**
- Creates a launchd plist with `RunAtLoad=true` and `KeepAlive=true`
- Loads the service via `launchctl load`

**Linux:**
- Creates a systemd user unit with `Restart=on-failure`
- Enables the service via `systemctl --user enable`
- Runs `loginctl enable-linger` so the service survives logout

### `aigernon daemon uninstall`

Stops the daemon (if running) and removes the service file.

### `aigernon daemon start`

Starts the daemon using the system service manager.

### `aigernon daemon stop`

Stops the daemon gracefully. The daemon will:
1. Stop accepting new messages
2. Wait for any active agent turn to complete (up to 30 seconds)
3. Flush pending session writes
4. Clean up PID and status files
5. Exit with code 0

If the 30-second timeout is exceeded, the daemon force-exits with code 1.

### `aigernon daemon restart`

Stops and starts the daemon.

### `aigernon daemon status`

Shows daemon status including:
- Platform and installation status
- Running state with PID
- Uptime
- Last heartbeat timestamp
- Active channels
- Active session count
- Log file location

Example output:
```
🐁 Daemon Status

Platform: macOS (launchd)
Installed: ✓ /Users/you/Library/LaunchAgents/com.aigernon.gateway.plist
Running: ✓ (PID 12345)
Uptime: 2h 15m
Last heartbeat: 45s ago
Channels: telegram
Active sessions: 3
Logs: /Users/you/.aigernon/logs/daemon.log
```

### `aigernon daemon logs`

Tails the daemon log file.

Options:
- `-n, --lines N` — Number of lines to show (default: 50)
- `-f, --follow` — Follow log output (like `tail -f`)

```bash
# Show last 100 lines
aigernon daemon logs -n 100

# Follow logs in real-time
aigernon daemon logs -f
```

## Health Check

The `aigernon doctor` command runs comprehensive health checks:

```bash
aigernon doctor
```

Example output:
```
AIGernon Health Check
=====================

✓ Config file exists (~/.aigernon/config.json)
✓ Config is valid JSON
✓ LLM provider configured (openrouter)
⚠ No web search API key configured
✓ Daemon is running (PID 12345, uptime 2h 15m)
✓ Last heartbeat: 45 seconds ago
✓ Telegram channel configured
⚠ No other channels configured
✓ Workspace exists (~/.aigernon/workspace/)
✓ Memory directory exists
✓ 3 skills loaded
✓ Cron: 2 jobs scheduled

Overall: Healthy (2 warnings)
```

Exit codes:
- `0` — Healthy (warnings are OK)
- `1` — Errors found

## Status Tracking

While running, the daemon maintains two files:

### `~/.aigernon/daemon.pid`

Contains the process ID. Used to verify the daemon is actually running.

### `~/.aigernon/daemon.status.json`

Updated every 60 seconds with:

```json
{
  "pid": 12345,
  "started_at": "2026-02-14T10:30:00+00:00",
  "last_heartbeat": "2026-02-14T11:45:00+00:00",
  "version": "0.1.0",
  "channels_active": ["telegram"],
  "sessions_active": 3
}
```

## Log Management

Logs are written to `~/.aigernon/logs/daemon.log`.

The daemon includes built-in log rotation:
- Rotates when log exceeds 10MB
- Keeps up to 3 rotated files (`daemon.log.1`, `daemon.log.2`, `daemon.log.3`)

## Graceful Shutdown

When the daemon receives SIGTERM or SIGINT:

1. **Stop accepting new messages** — Channels stop polling/listening
2. **Wait for active turns** — Any in-progress agent response completes (30s timeout)
3. **Flush sessions** — Pending writes are persisted
4. **Cleanup** — PID and status files are removed
5. **Exit** — Code 0 (graceful) or 1 (timeout exceeded)

This ensures conversations aren't cut off mid-response.

## Environment Variables

The service file passes through these environment variables if set:

- `OPENROUTER_API_KEY`
- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GROQ_API_KEY`
- `BRAVE_API_KEY`
- `PATH`
- `HOME`

If your API keys are in `~/.aigernon/config.json`, you don't need environment variables.

## Auto-Restart Behavior

**macOS (launchd):**
- `KeepAlive=true` — Restarts immediately on crash
- `ThrottleInterval=10` — Prevents rapid restart loops (min 10s between restarts)

**Linux (systemd):**
- `Restart=on-failure` — Restarts only on non-zero exit
- `RestartSec=10` — Waits 10 seconds before restarting

## Troubleshooting

### Service won't start

1. Check if another instance is running:
   ```bash
   ps aux | grep aigernon
   ```

2. Check the logs:
   ```bash
   aigernon daemon logs -n 100
   ```

3. Verify config is valid:
   ```bash
   aigernon doctor
   ```

### macOS: "Operation not permitted"

Grant Terminal (or your IDE) Full Disk Access in System Preferences → Security & Privacy → Privacy.

### Linux: Service doesn't survive logout

Ensure linger is enabled:
```bash
loginctl enable-linger $USER
```

### Daemon starts but channels don't connect

1. Check channel configuration:
   ```bash
   aigernon channels status
   ```

2. Verify API tokens in `~/.aigernon/config.json`

3. Check daemon logs for connection errors:
   ```bash
   aigernon daemon logs | grep -i error
   ```

## Manual Operation

If daemon management isn't supported on your platform, run the gateway manually:

```bash
# Foreground (for debugging)
aigernon gateway

# Background with nohup
nohup aigernon gateway > ~/.aigernon/logs/daemon.log 2>&1 &

# With screen/tmux
screen -dmS aigernon aigernon gateway
```

Or use Docker:
```bash
docker run -d \
  --restart=unless-stopped \
  -v ~/.aigernon:/root/.aigernon \
  aigernon gateway
```
