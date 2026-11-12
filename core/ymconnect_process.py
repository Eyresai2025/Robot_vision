"""Separate managed YMConnect bridge per physical controller.

Runs only upon deliberate user request after explicit config enablement.
Never implements motion, servo, job control, writes, or auto-connect.
"""
import json
import ipaddress
from pathlib import Path
from PySide6.QtCore import QObject, QProcess, Signal

BASE = Path(__file__).resolve().parents[1]
CONFIG = BASE / 'config' / 'hardware_readonly.json'


def load_hardware_settings():
    defaults = {'enabled': False, 'sdk_dll': '', 'bridge_executable': '',
                'poll_interval_ms': 1000, 'approved_read_variables': []}
    if not CONFIG.exists():
        return defaults
    return {**defaults, **json.loads(CONFIG.read_text(encoding='utf-8'))}


class HardwareRobot(QObject):
    sample = Signal(int, dict)
    note = Signal(int, str)
    state = Signal(int, str)

    def __init__(self, robot_id, parent=None):
        super().__init__(parent)
        self.robot_id = robot_id
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self.process.readyReadStandardOutput.connect(self._stdout)
        self.process.readyReadStandardError.connect(self._stderr)
        self.process.finished.connect(self._finished)
        self._buf = ''
        self.connection_state = 'Offline'
        self.last_sample = {}

    def connect_readonly(self, ip):
        cfg = load_hardware_settings()
        if not cfg.get('enabled'):
            raise RuntimeError('Hardware reads disabled in config/hardware_readonly.json')
        sdk, exe = Path(cfg['sdk_dll']), Path(cfg['bridge_executable'])
        if not sdk.is_file() or not exe.is_file():
            raise FileNotFoundError('Install official YMConnect .NET DLL and build bridge; set both paths in hardware_readonly.json')
        ip = str(ipaddress.IPv4Address(ip))
        if self.process.state() != QProcess.ProcessState.NotRunning:
            raise RuntimeError('Controller connection already active')
        allowed = cfg.get('approved_read_variables', [])
        if not isinstance(allowed, list) or any(not isinstance(x,str) for x in allowed):
            raise ValueError('approved_read_variables must be a list of register strings')
        args = ['--ip', ip, '--sdk', str(sdk), '--reads', ','.join(allowed),
                '--interval', str(max(250, int(cfg.get('poll_interval_ms',1000))))]
        self.connection_state = 'Connecting'
        self.state.emit(self.robot_id, self.connection_state)
        self._buf = ''
        self.process.start(str(exe), args)
        if not self.process.waitForStarted(1000):
            self.connection_state = 'Offline'
            raise RuntimeError(self.process.errorString())

    def disconnect_readonly(self):
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()  # Stop PC-side reader process; no command is sent to robot.
        self.connection_state = 'Offline'
        self.state.emit(self.robot_id, self.connection_state)

    def _stdout(self):
        self._buf += bytes(self.process.readAllStandardOutput()).decode('utf-8','replace')
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            try: message = json.loads(line)
            except json.JSONDecodeError:
                self.note.emit(self.robot_id, 'Bridge emitted invalid JSON')
                continue
            kind = message.get('kind')
            if kind == 'connected':
                self.connection_state = 'Connected (read-only)'
                self.state.emit(self.robot_id, self.connection_state)
                self.note.emit(self.robot_id, f"Connected to {message.get('ip')} — open {message.get('connection_ms')} ms")
            elif kind == 'sample':
                self.last_sample = message
                self.sample.emit(self.robot_id, message)
            elif kind == 'error':
                self.note.emit(self.robot_id, 'YMConnect error: '+str(message.get('message')))

    def _stderr(self):
        err = bytes(self.process.readAllStandardError()).decode('utf-8','replace').strip()
        if err: self.note.emit(self.robot_id, 'Bridge stderr: '+err[-500:])

    def _finished(self, code, status):
        self.connection_state = 'Offline'
        self.state.emit(self.robot_id, self.connection_state)
        self.note.emit(self.robot_id, f'Read-only bridge exited, code={code}')
