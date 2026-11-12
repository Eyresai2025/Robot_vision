"""Safe dual-robot telemetry demo. No network traffic or controller writes.

A future Yaskawa adapter must be installed separately after confirming controller
model, approved register ownership and read permissions. These values represent
virtual controllers only, never physical robot measurements.
"""
from __future__ import annotations
import json
import ipaddress
import statistics
import time
from collections import deque
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal

DEFAULT_IPS = {1: '192.168.1.101', 2: '192.168.1.102'}  # examples, NOT discovered
CHECKPOINTS = {'sidewall1':101, 'inner':102, 'tread':201, 'bead':202, 'sidewall2':203}
CONFIG_PATH = Path(__file__).resolve().parents[1] / 'config' / 'robot_connections.json'


class VirtualRobot(QObject):
    updated = Signal(int, dict)
    note = Signal(int, str)

    def __init__(self, robot_id: int, parent=None):
        super().__init__(parent)
        self.robot_id = robot_id
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.poll)
        self.connected = False
        self.heartbeat = 0
        self.current_cp = 0
        self.request_token = 0
        self.capture_req = 0
        self.capture_result = 0
        self.result_valid = 0
        self.result_token = 0
        self.cycle_done = 0
        self.robot_error = 0
        self._last_poll = None
        self._poll_count = 0
        self.intervals = deque(maxlen=500)
        self.emit_state()

    def connect_virtual(self):
        self.connected = True
        self._last_poll = None
        self.intervals.clear()
        self.timer.start()
        self.note.emit(self.robot_id, 'Virtual robot connected; no network connection opened.')
        self.emit_state()

    def disconnect_virtual(self):
        self.timer.stop()
        self.connected = False
        self._last_poll = None
        self.note.emit(self.robot_id, 'Virtual robot disconnected.')
        self.emit_state()

    def poll(self):
        if not self.connected:
            return
        now = time.perf_counter()
        if self._last_poll is not None:
            self.intervals.append((now - self._last_poll) * 1000)
        self._last_poll = now
        self.heartbeat = (self.heartbeat + 1) % 65536
        self._poll_count += 1
        if self._poll_count % 5 == 0:
            self.emit_state()

    def cycle_start(self):
        self.cycle_done = 0
        self.current_cp = 0
        self.request_token = 0
        self.capture_req = 0
        self.capture_result = 0
        self.result_valid = 0
        self.result_token = 0
        self.emit_state()

    def on_checkpoint(self, view: str, phase: str):
        if not self.connected:
            return
        cp = CHECKPOINTS.get(view)
        if cp is None:
            return
        if phase == 'CAPTURING':
            self.current_cp = cp
            self.request_token += 1
            self.capture_req = 1
            self.capture_result = 0
            self.result_valid = 0
            self.note.emit(self.robot_id, f'Virtual checkpoint {cp}: request token {self.request_token}.')
        elif phase == 'DONE':
            self.capture_result = 1  # simulated image saved, NOT tyre quality
            self.result_token = self.request_token
            self.result_valid = 1
            self.capture_req = 0
            self.note.emit(self.robot_id, f'Virtual capture complete: checkpoint {cp}, token {self.result_token}.')
        self.emit_state()

    def cycle_finish(self, success: bool):
        self.cycle_done = 1 if success else 0
        self.emit_state()

    def snapshot(self):
        vals = list(self.intervals)
        p95 = sorted(vals)[min(len(vals) - 1, int(0.95 * len(vals)))] if vals else None
        return {
            'connected': self.connected, 'mode': 'SIMULATION',
            'registers': {'B010': int(self.connected), 'B013': self.capture_req,
                          'B011': self.capture_result, 'B012': self.result_valid,
                          'B014': self.cycle_done, 'I010': self.heartbeat,
                          'I011': self.current_cp, 'I012': self.request_token,
                          'I013': self.result_token, 'I014': self.robot_error},
            'samples': len(vals), 'poll_mean_ms': round(statistics.mean(vals), 1) if vals else None,
            'poll_p95_ms': round(p95, 1) if p95 is not None else None,
            'poll_max_ms': round(max(vals), 1) if vals else None,
        }

    def emit_state(self):
        self.updated.emit(self.robot_id, self.snapshot())


def load_addresses():
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
            return {idx: str(saved.get(f'robot{idx}', DEFAULT_IPS[idx])) for idx in (1, 2)}
        except (OSError, ValueError):
            pass
    return DEFAULT_IPS.copy()


def save_addresses(addresses):
    for address in addresses.values():
        ipaddress.ip_address(address.strip())
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({f'robot{k}': str(v).strip() for k, v in addresses.items()}, indent=2), encoding='utf-8')
