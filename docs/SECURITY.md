# Security

AIGernon includes a comprehensive security module to protect against abuse, injection attacks, and unauthorized modifications.

## Overview

The security module (`aigernon/security/`) provides four key components:

| Component | Purpose |
|-----------|---------|
| `RateLimiter` | Prevents message flooding and abuse |
| `AuditLogger` | Records all security-relevant events |
| `IntegrityMonitor` | Detects unauthorized file modifications |
| `InputSanitizer` | Blocks injection attacks |

---

## Rate Limiting

Per-user rate limiting with sliding window and burst protection.

### Configuration

In `config.json`:

```json
{
  "security": {
    "rate_limit": {
      "enabled": true,
      "max_requests": 30,
      "window_seconds": 60,
      "burst_limit": 5,
      "burst_window_seconds": 5
    }
  }
}
```

### Behavior

- **Window limit**: Maximum requests per rolling time window (default: 30/minute)
- **Burst limit**: Maximum rapid requests (default: 5 in 5 seconds)
- Automatic cleanup of stale tracking data
- Per-user statistics available via `get_stats(user_id)`

### Response

When rate limited, users receive a message explaining the limit and suggesting they wait before retrying.

---

## Audit Logging

All tool invocations and security events are logged to daily rotating JSONL files.

### Log Location

```
~/.aigernon/audit/audit-YYYY-MM-DD.jsonl
```

### Logged Events

| Event Type | Description |
|------------|-------------|
| `tool_call` | Every tool invocation with parameters |
| `access_denied` | Unauthorized access attempts |
| `rate_limited` | Rate limit violations |
| `security_event` | Integrity violations, suspicious inputs |

### Example Entry

```json
{
  "timestamp": "2025-01-15T10:30:00.000000",
  "event": "tool_call",
  "tool": "exec",
  "params": {"command": "ls -la"},
  "user_id": "telegram:123456",
  "channel": "telegram",
  "session_key": "abc123",
  "success": true
}
```

### Sensitive Data Handling

Parameters containing sensitive keys (`password`, `token`, `api_key`, etc.) are automatically redacted in logs.

---

## Integrity Monitoring

SHA-256 hash verification for critical configuration files to detect unauthorized modifications.

### Monitored Files

By default, the following files are monitored:

- `SOUL.md` - Agent identity and behavior
- `AGENTS.md` - Agent definitions
- `IDENTITY.md` - Identity configuration
- `USER.md` - User profile
- `config.json` - Main configuration

### Hash Storage

```
~/.aigernon/security/integrity_hashes.json
```

### Usage

**Initialize baselines** (run after authorized changes):

```python
from aigernon.security import IntegrityMonitor

monitor = IntegrityMonitor(workspace_path)
monitor.initialize()  # Creates baseline hashes
```

**Verify integrity**:

```python
violations = monitor.verify()
if violations:
    for v in violations:
        print(f"Modified: {v['file']}")
```

**Update after authorized change**:

```python
monitor.update_hash(Path("~/.aigernon/workspace/SOUL.md"))
```

### Violation Handling

When a violation is detected:
1. Event is logged to audit log
2. Optional callback is triggered (`on_violation`)
3. Details include: file path, expected hash, actual hash

---

## Input Sanitization

Protection against injection attacks and malicious inputs.

### Detected Patterns

**General (all inputs)**:
- Shell metacharacters (`;`, `|`, `&`, `` ` ``, `$`)
- Command substitution (`$(...)`, `` `...` ``)
- Path traversal (`../`)
- Null bytes (`\x00`)
- ANSI escape sequences

**Command-specific** (exec tool):
- Recursive root deletion (`rm -rf /`)
- Sudo usage
- Insecure permissions (`chmod 777`)
- Curl/wget pipe to shell
- Direct disk writes
- Fork bombs
- System power commands

### Input Length Limits

| Type | Max Length |
|------|------------|
| Command | 10,000 chars |
| Path | 4,096 chars |
| Content | 1,000,000 chars (1MB) |
| Default | 50,000 chars |

### Strict Mode

Enable strict mode to block on any warning (not just critical patterns):

```python
sanitizer = InputSanitizer(strict_mode=True)
```

### Example

```python
from aigernon.security import InputSanitizer

sanitizer = InputSanitizer()
result = sanitizer.sanitize_string("ls; rm -rf /", input_type="command")

if not result.safe:
    print(f"Blocked: {result.blocked_reason}")
else:
    for warning in result.warnings:
        print(f"Warning: {warning}")
```

---

## Architecture

```
aigernon/security/
├── __init__.py          # Public exports
├── rate_limiter.py      # RateLimiter, RateLimitConfig
├── audit.py             # AuditLogger
├── integrity.py         # IntegrityMonitor, IntegrityConfig
└── sanitizer.py         # InputSanitizer, SanitizationResult
```

### Integration Points

The security module integrates with:

- **Channel handlers**: Rate limiting and audit logging on incoming messages
- **Tool registry**: Input sanitization before tool execution
- **Agent loop**: Audit logging of tool calls and results
- **Daemon startup**: Integrity verification on boot

---

## Best Practices

1. **Initialize integrity baselines** after configuring AIGernon
2. **Review audit logs** periodically for suspicious activity
3. **Adjust rate limits** based on expected usage patterns
4. **Enable strict mode** for high-security deployments
5. **Protect the security directory** (`~/.aigernon/security/`) with appropriate permissions

---

## Related

- [Daemon & Service](DAEMON.md) - Running AIGernon securely as a service
- [Main README](../README.md) - Project overview
