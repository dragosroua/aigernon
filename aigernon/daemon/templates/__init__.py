"""Service file templates for daemon management."""

LAUNCHD_PLIST = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.aigernon.gateway</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>aigernon.cli</string>
        <string>gateway</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>WorkingDirectory</key>
    <string>{working_dir}</string>

    <key>StandardOutPath</key>
    <string>{log_file}</string>

    <key>StandardErrorPath</key>
    <string>{log_file}</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>{path_env}</string>
        <key>HOME</key>
        <string>{home}</string>
{extra_env_entries}
    </dict>
</dict>
</plist>
"""

SYSTEMD_UNIT = """\
[Unit]
Description=AIGernon Gateway Service
After=network.target

[Service]
Type=simple
ExecStart={python_path} -m aigernon.cli gateway
WorkingDirectory={working_dir}
Restart=on-failure
RestartSec=10

StandardOutput=append:{log_file}
StandardError=append:{log_file}

Environment="PATH={path_env}"
Environment="HOME={home}"
{extra_env_lines}

[Install]
WantedBy=default.target
"""
