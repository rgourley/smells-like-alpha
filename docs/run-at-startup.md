# Keep a fly running

`flybrain loop 001 --go` trades on the fly's schedule for as long as it runs. It checks every five minutes whether a session is due, and one session runs per slot. To have it start with the machine and restart after a crash, hand it to the system's scheduler. A crypto fly on an `<N>h` cadence catches up: if the machine was asleep at the top of a window, the session runs as soon as it wakes, once per window. A daily stock fly has to be awake between 15:30 and 16:00 New York time, because an order does not fill after the close. On a Mac, `caffeinate -is` in front of the command keeps a plugged-in machine awake.

An order's idempotency key is made from the session hour, so a restart in the same hour cannot fill the same order twice.

## macOS

Save this as `~/Library/LaunchAgents/flybrain.001.plist`, with your own path in place of `/path/to/smells-like-alpha`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>flybrain.001</string>
  <key>ProgramArguments</key><array>
    <string>/path/to/smells-like-alpha/.venv/bin/flybrain</string><string>loop</string><string>001</string><string>--go</string>
  </array>
  <key>WorkingDirectory</key><string>/path/to/smells-like-alpha</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>300</integer>
  <key>StandardOutPath</key><string>/path/to/smells-like-alpha/flies/001/run.log</string>
  <key>StandardErrorPath</key><string>/path/to/smells-like-alpha/flies/001/run.log</string>
</dict></plist>
```

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/flybrain.001.plist
```

To stop it: `launchctl bootout gui/$(id -u)/flybrain.001`.

## Windows

In PowerShell, with your own path:

```powershell
$action = New-ScheduledTaskAction -Execute "C:\path\to\smells-like-alpha\.venv\Scripts\flybrain.exe" -Argument "loop 001 --go" -WorkingDirectory "C:\path\to\smells-like-alpha"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 5) -ExecutionTimeLimit 0
Register-ScheduledTask -TaskName "flybrain 001" -Action $action -Trigger $trigger -Settings $settings
```

To stop it: `Unregister-ScheduledTask -TaskName "flybrain 001"`.

## Linux

A systemd user service with `Restart=always` and `ExecStart=/path/to/smells-like-alpha/.venv/bin/flybrain loop 001 --go` does the same job.
