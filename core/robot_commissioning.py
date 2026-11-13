"""Offline hardware readiness and persistent event logging; never opens network connections."""
from __future__ import annotations
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
LOG_DIR = BASE / 'data' / 'diagnostics'
EVENT_FILE = LOG_DIR / 'robot_communication_events.csv'
FIELDS = ['timestamp','robot_id','mode','event','detail']
VAR = re.compile(r'^[BI]\d{1,4}$', re.IGNORECASE)


def append_event(robot_id, mode, event, detail=''):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with EVENT_FILE.open('a', encoding='utf-8-sig' if not EVENT_FILE.exists() else 'utf-8', newline='') as f:
        writer = csv.writer(f)
        if f.tell() == 0: writer.writerow(FIELDS)
        writer.writerow([datetime.now(timezone.utc).isoformat(), robot_id, mode, event, str(detail)[:2000]])


def readiness(config_path=None, check_sdk=False):
    """Read filesystem and optional offline assembly inspection; no ping or robot contact."""
    CONFIG = BASE / 'config' / 'hardware_readonly.json'
    import subprocess
    path = Path(config_path) if config_path else CONFIG
    checks = []
    def add(name, ok, explanation):
        checks.append({'name':name, 'ok':bool(ok), 'detail':explanation})
    try:
        settings = json.loads(path.read_text(encoding='utf-8'))
        add('Hardware configuration', True, 'Configuration JSON loaded')
    except (OSError, ValueError) as ex:
        settings = {}
        add('Hardware configuration', False, str(ex))
    sdk = Path(str(settings.get('sdk_dll') or ''))
    exe = Path(str(settings.get('bridge_executable') or ''))
    add('YMConnect .NET assembly', sdk.is_file(), str(sdk) if sdk.is_file() else 'SDK DLL missing or path not configured')
    native = sdk.parent / 'YMConnect.dll'
    add('YMConnect native library', sdk.is_file() and native.is_file(), str(native) if native.is_file() else 'Native DLL absent alongside SDK')
    add('Published read-only bridge', exe.is_file(), str(exe) if exe.is_file() else 'Bridge executable missing')
    try:
        interval = int(settings.get('poll_interval_ms', 1000))
        valid_interval = 250 <= interval <= 10000
    except (TypeError, ValueError):
        valid_interval = False
    add('Polling configuration', valid_interval, 'Expected 250–10000 ms')
    reads = settings.get('approved_read_variables', [])
    valid = isinstance(reads, list) and len(reads) <= 24 and all(isinstance(v, str) and VAR.fullmatch(v) for v in reads)
    add('Approved read-list format', valid, f'{len(reads) if isinstance(reads, list) else 0} configured references; approval still required')
    add('Hardware access safely disabled', not bool(settings.get('enabled', False)), 'Disabled (safe offline default)' if not settings.get('enabled') else 'Enabled: confirm commissioning authorization')
    if check_sdk and sdk.is_file() and exe.is_file():
        try:
            outcome = subprocess.run([str(exe),'--inspect','--sdk',str(sdk)],capture_output=True,text=True,timeout=8,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            ok = outcome.returncode == 0 and any(json.loads(line).get('kind')=='sdk_loaded' for line in outcome.stdout.splitlines() if line.startswith('{'))
            add('Offline SDK inspection', ok, 'sdk_loaded confirmed; no network traffic' if ok else (outcome.stderr or outcome.stdout)[-350:])
        except (OSError, ValueError, subprocess.TimeoutExpired) as ex:
            add('Offline SDK inspection', False, str(ex))
    return checks


def simulate_commissioning():
    """Deterministic sample transitions for UI validation, no worker or network calls."""
    return [
        ('Robot 1', 'Offline', 'No hardware session opened'),
        ('Robot 1', 'Connecting', 'Simulated delayed response'),
        ('Robot 1', 'Connected (test only)', 'Synthetic state sample, not a controller result'),
        ('Robot 1', 'Stale', 'Simulated sample age exceeds watchdog limit'),
        ('Robot 1', 'Offline', 'Simulated connection closed'),
        ('Robot 2', 'Error', 'Simulated missing SDK / timeout path'),
    ]
