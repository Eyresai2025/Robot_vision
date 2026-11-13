"""Two separate read-only YMConnect bridge workers with stale-data watchdog.

No robot writes, auto-connect at launch, motion, servo or job operations.
Auto-reconnect is opt-in and bounded; deliberate disconnect disarms it.
"""
import json
import ipaddress
import time
import re
from pathlib import Path
from collections import deque
from statistics import mean
from PySide6.QtCore import QObject, QProcess, QTimer, Signal

BASE = Path(__file__).resolve().parents[1]
CONFIG = BASE / 'config' / 'hardware_readonly.json'


def load_hardware_settings():
    defaults = {'enabled': False, 'sdk_dll': '', 'bridge_executable': '',
                'poll_interval_ms': 1000, 'approved_read_variables': [],
                'stale_timeout_ms': 3500, 'auto_reconnect': False,
                'max_reconnect_attempts': 3, 'reconnect_delay_ms': 3000}
    if not CONFIG.exists(): return defaults
    value = json.loads(CONFIG.read_text(encoding='utf-8'))
    if not isinstance(value, dict): raise ValueError('hardware_readonly.json must contain a JSON object')
    return {**defaults, **value}


class HardwareRobot(QObject):
    sample = Signal(int, dict)
    note = Signal(int, str)
    state = Signal(int, str)
    metrics = Signal(int, dict)

    def __init__(self, robot_id, parent=None):
        super().__init__(parent)
        self.robot_id = robot_id
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._stdout)
        self.process.readyReadStandardError.connect(self._stderr)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._process_error)
        self._buf = ''
        self.connection_state = 'Offline'
        self.last_sample = {}
        self._last_sample_monotonic = None
        self._started_monotonic = None
        self.samples = deque(maxlen=500)
        self._armed = False
        self._ip = ''
        self._retries = 0
        self._cfg = {}
        self.watchdog = QTimer(self)
        self.watchdog.setInterval(500)
        self.watchdog.timeout.connect(self._check_watchdog)
        self.retry_timer = QTimer(self)
        self.retry_timer.setSingleShot(True)
        self.retry_timer.timeout.connect(self._retry)

    def _set_state(self, value):
        if self.connection_state != value:
            self.connection_state = value
            self.state.emit(self.robot_id, value)

    def connect_readonly(self, ip):
        cfg = load_hardware_settings()
        if not cfg.get('enabled'):
            raise RuntimeError('Hardware reads disabled in config/hardware_readonly.json')
        sdk, exe = Path(str(cfg.get('sdk_dll',''))), Path(str(cfg.get('bridge_executable','')))
        if not sdk.is_file() or not exe.is_file():
            raise FileNotFoundError('YMConnect SDK or published read-only bridge missing; configure paths first')
        ip = str(ipaddress.IPv4Address(ip))
        if self.process.state() != QProcess.ProcessState.NotRunning:
            raise RuntimeError('Controller connection already active')
        allowed = cfg.get('approved_read_variables', [])
        if not isinstance(allowed, list) or len(allowed)>24 or any(not isinstance(v,str) or not re.fullmatch(r'[BI]\d{1,4}',v,re.I) for v in allowed):
            raise ValueError('approved_read_variables must contain at most 24 B/I register references')
        self._cfg = cfg
        self._ip = ip
        self._armed = True
        self._retries = 0
        self._launch()

    def _launch(self):
        if not self._armed or not load_hardware_settings().get('enabled'):
            self._set_state('Offline')
            return
        cfg = self._cfg
        args = ['--ip', self._ip, '--sdk', str(cfg['sdk_dll']), '--reads', ','.join(cfg['approved_read_variables']),
                '--interval', str(max(250,min(10000,int(cfg.get('poll_interval_ms',1000)))))]
        self._buf = ''
        self._started_monotonic = time.monotonic()
        self._last_sample_monotonic = None
        self.last_sample = {}
        self._set_state('Connecting')
        self.watchdog.start()
        self.process.start(str(cfg['bridge_executable']), args)
        # asynchronous QProcess; never block the GUI waiting for a connection

    def disconnect_readonly(self):
        self._armed = False
        self.retry_timer.stop()
        self.watchdog.stop()
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()  # Only stops local PC reader, sends NO robot instruction.
        self._last_sample_monotonic = None
        self.last_sample = {}
        self._set_state('Offline')

    def _stdout(self):
        self._buf += bytes(self.process.readAllStandardOutput()).decode('utf-8','replace')
        if len(self._buf) > 131072:
            self._buf = ''
            self.note.emit(self.robot_id, 'Oversized bridge output discarded')
            return
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            try:
                message = json.loads(line)
                if not isinstance(message,dict): raise ValueError('Not a JSON object')
            except (json.JSONDecodeError,ValueError):
                self.note.emit(self.robot_id, 'Bridge returned invalid JSON')
                continue
            kind = message.get('kind')
            if kind == 'connected':
                if not message.get('status_verified',False):
                    self.note.emit(self.robot_id, 'SDK connected but returned unverified connection status')
                self._set_state('Connected (read-only)')
                self._retries = 0
                self.note.emit(self.robot_id, f"Connected to {message.get('ip')} — SDK open {message.get('connection_ms')} ms")
            elif kind == 'sample':
                self._last_sample_monotonic = time.monotonic()
                self.last_sample = message
                val = message.get('elapsed_ms')
                if isinstance(val,(int,float)) and val>=0:
                    self.samples.append(float(val))
                if self.connection_state == 'Stale': self._set_state('Connected (read-only)')
                self.sample.emit(self.robot_id, message)
                self.metrics.emit(self.robot_id, self.snapshot_metrics())
            elif kind == 'error':
                self.note.emit(self.robot_id, 'YMConnect error: '+str(message.get('message')))
            else:
                self.note.emit(self.robot_id, 'Unrecognized bridge event '+str(kind))

    def snapshot_metrics(self):
        values = sorted(self.samples)
        return {'count':len(values), 'mean_ms':round(mean(values),2) if values else None,
                'p95_ms':round(values[max(0,int((len(values)-1)*.95))],2) if values else None,
                'max_ms':round(values[-1],2) if values else None,
                'sample_age_ms':round((time.monotonic()-self._last_sample_monotonic)*1000) if self._last_sample_monotonic else None}

    def _check_watchdog(self):
        if not self._armed: return
        threshold = max(1000,int(self._cfg.get('stale_timeout_ms',3500)))/1000
        now = time.monotonic()
        since = self._last_sample_monotonic if self._last_sample_monotonic else self._started_monotonic
        if since and now-since>threshold and self.connection_state in ('Connected (read-only)','Connecting'):
            self._set_state('Stale')
            self.note.emit(self.robot_id, f'Watchdog: no fresh successful sample in {threshold:.1f}s; values must not be treated as live')
            if self.process.state()!=QProcess.ProcessState.NotRunning:
                self.process.kill()  # Local process only; reconnect handled after finished

    def _stderr(self):
        err = bytes(self.process.readAllStandardError()).decode('utf-8','replace').strip()
        if err: self.note.emit(self.robot_id, 'Bridge stderr: '+err[-500:])

    def _process_error(self, error):
        self.note.emit(self.robot_id, 'Bridge process error: '+self.process.errorString())

    def _finished(self, code, status):
        self.watchdog.stop()
        self._last_sample_monotonic = None
        self.last_sample = {}
        self._set_state('Offline')
        self.note.emit(self.robot_id, f'Read-only bridge exited, code={code}')
        if self._armed and self._cfg.get('auto_reconnect',False) and load_hardware_settings().get('enabled',False):
            maximum = max(0,min(10,int(self._cfg.get('max_reconnect_attempts',3))))
            if self._retries < maximum:
                self._retries+=1
                delay = max(1000,min(30000,int(self._cfg.get('reconnect_delay_ms',3000))))
                self.note.emit(self.robot_id, f'Opt-in retry {self._retries}/{maximum} scheduled in {delay} ms')
                self.retry_timer.start(delay)
            else:
                self._armed = False
                self.note.emit(self.robot_id, 'Retry limit reached; manual reconnect required')
        else:
            self._armed = False

    def _retry(self):
        if self._armed and self.process.state() == QProcess.ProcessState.NotRunning:
            self._launch()
