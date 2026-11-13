"""Manual / Robot Ready → software capture UX; no motion or I/O writes.

Offline tests are performed with synthetic images. Real ready-bit gating uses
read-only YMConnect samples, and is disabled until a healthy, approved live
read session exists. No camera SDK acquisition is performed in this module.
"""
from __future__ import annotations
import time
from PySide6.QtCore import Qt,QTimer,QThread,Signal
from PySide6.QtWidgets import (QFrame,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,
    QComboBox,QPushButton,QMessageBox,QCheckBox)
from core import sku_store
from core.camera_profiles import apply_ready_gate
from core.software_capture import CAPTURE_LEASE


class CaptureTask(QThread):
    capture_result=Signal(dict)
    capture_error=Signal(str)
    def __init__(self,recipe,view,profile,barcode,mode):
        super().__init__()
        self.recipe=recipe;self.view=view;self.profile=profile;self.barcode=barcode;self.mode=mode
    def run(self):
        try:
            outcome=CAPTURE_LEASE.capture(self.recipe['sku'],self.recipe['version'],
                self.view,self.profile,self.barcode,mode=self.mode)
            self.capture_result.emit(outcome)
        except Exception as ex:self.capture_error.emit(str(ex))

class SoftwareCapturePanel(QFrame):
    def __init__(self,robot_workers, parent=None):
        super().__init__(parent)
        self.setObjectName('stationCard')
        self.robots=robot_workers
        self.record=None
        self._armed=False
        self._task=None
        self._last_bit=None
        self._arm_time=0.0
        self._last_fired_token=None
        l=QVBoxLayout(self);l.setContentsMargins(18,18,18,18);l.setSpacing(9)
        heading=QLabel('Software Capture — Manual / Robot Ready Bit');heading.setStyleSheet('font-size:17px;font-weight:800')
        l.addWidget(heading)
        desc=QLabel('Offline bench controls. Both choices use a software start. Robot Ready reads an authorized B/I variable; it does not write robot I/O.');desc.setWordWrap(True);l.addWidget(desc)
        r=QHBoxLayout();l.addLayout(r)
        self.barcode=QLineEdit('CAM_TEST_001');self.barcode.setPlaceholderText('Test barcode');r.addWidget(self.barcode,2)
        self.sku=QComboBox();r.addWidget(self.sku,3)
        self.view=QComboBox();
        for v in sku_store.VIEWS:self.view.addItem(sku_store.VIEW_NAMES[v],v)
        r.addWidget(self.view,2)
        self.info=QLabel('');self.info.setWordWrap(True);l.addWidget(self.info)
        action=QHBoxLayout();l.addLayout(action)
        self.manual=QPushButton('Manual Software Capture (Test)');self.manual.setObjectName('primary');action.addWidget(self.manual)
        self.arm=QPushButton('Arm Robot Ready Mode');action.addWidget(self.arm)
        self.offline=QPushButton('Simulate Ready Edge (Offline)');action.addWidget(self.offline)
        self.cancel=QPushButton('Disarm');action.addWidget(self.cancel)
        self.status=QLabel('No acquisition armed');self.status.setWordWrap(True);l.addWidget(self.status)
        l.addWidget(QLabel('Test output: data/camera_software_tests/<barcode>/<SKU_vN>/<timestamp>/. Real camera/robot integration remains disabled.'))
        self.manual.clicked.connect(self.manual_test)
        self.arm.clicked.connect(self.arm_gate)
        self.offline.clicked.connect(self.offline_test)
        self.cancel.clicked.connect(self.disarm)
        self.sku.currentIndexChanged.connect(self.on_choice)
        self.view.currentIndexChanged.connect(self.on_choice)
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self.watch_ready);self.timer.start()
        self.refresh()

    def refresh(self):
        prev=self.sku.currentData()
        self.sku.blockSignals(True);self.sku.clear()
        for code,display,ver in sku_store.selectable_skus():
            if ver>0:self.sku.addItem(display,(code,ver))
        idx=self.sku.findData(prev);self.sku.setCurrentIndex(idx if idx>=0 else (0 if self.sku.count() else -1))
        self.sku.blockSignals(False);self.on_choice()

    def on_choice(self,*_):
        self.disarm();key=self.sku.currentData()
        self.record=sku_store.get_recipe(*key) if key else None
        view=self.view.currentData()
        if not self.record:
            self.info.setText('Activate a valid simulation SKU first.');return
        from core.camera_profiles import normalize_profile,profile_checks,CAMERAS
        p=normalize_profile(self.record['recipe']['camera_profiles'][view]);err=profile_checks(p)
        self.info.setText(f'{self.record["sku"]} V{self.record["version"]} · {view} · {CAMERAS[view]} · '
                          f'{p["capture_mode"]} · {"Profile ready" if not err else "; ".join(err[:3])}')

    def selected(self):
        if not self.record:raise RuntimeError('Select a simulation-active SKU')
        from core.camera_profiles import normalize_profile
        view=self.view.currentData()
        p=normalize_profile(self.record['recipe']['camera_profiles'][view])
        return self.record,view,p

    def do_test(self,reason):
        if self._task is not None and self._task.isRunning():
            QMessageBox.warning(self,'Capture busy','A capture test is already running');return
        try:
            r,view,p=self.selected()
            # QImage creation and disk output happen in a worker, not the GUI thread.
            task=CaptureTask(r,view,p,self.barcode.text().strip(),reason)
            self._task=task
            for button in (self.manual,self.arm,self.offline):button.setEnabled(False)
            self.status.setText(f'{view} / {reason}: synthetic capture in progress...')
            task.capture_result.connect(self.test_complete)
            task.capture_error.connect(self.test_failed)
            task.finished.connect(self.test_thread_finished)
            task.start()
        except Exception as ex:
            self.status.setText('No capture: '+str(ex))
            QMessageBox.warning(self,'Capture test',str(ex))
        finally:self.disarm(keep_status=True)

    def test_complete(self,outcome):
        self.status.setText(f'SYNTHETIC TEST SAVED: {outcome["image"]}')

    def test_failed(self,message):
        self.status.setText('No capture: '+message)
        QMessageBox.warning(self,'Capture test',message)

    def test_thread_finished(self):
        for button in (self.manual,self.arm,self.offline):button.setEnabled(True)
        if self._task is not None:
            self._task.deleteLater()
            self._task=None

    def manual_test(self):
        try:
            _,_,p=self.selected()
            if p['capture_mode']!='MANUAL_SOFTWARE':
                raise ValueError('Selected view is Robot Ready mode; change recipe or use its ready-bit gate.')
        except Exception as ex:QMessageBox.warning(self,'Capture mode',str(ex));return
        self.do_test('MANUAL_SOFTWARE')

    def arm_gate(self):
        try:
            _,view,p=self.selected()
            if p['capture_mode']!='ROBOT_READY_SOFTWARE':raise ValueError('Selected view is not configured for robot ready-bit mode')
            if not p['ready_variable'] or not p['checkpoint_variable']:
                raise ValueError('Configure approved ready AND checkpoint variables first')
        except Exception as ex:QMessageBox.warning(self,'Cannot arm',str(ex));return
        self._armed=True;self._last_bit=None;self._arm_time=time.monotonic();self._last_fired_token=None
        self.status.setText('ARMED: waiting for a fresh, approved robot ready-bit transition with live sample')

    def watch_ready(self):
        if not self._armed:return
        if time.monotonic()-self._arm_time>30:
            self.disarm();self.status.setText('Disarmed: no valid ready event within 30 seconds');return
        r,view,p=self.selected()
        station,robot,_=sku_store.ASSIGNMENTS[view]
        worker=self.robots[int(robot[-1])]
        sample=worker.last_sample or {}
        vals=sample.get('variables') or {}
        results=sample.get('variable_results') or {}
        key=p['ready_variable'].upper()
        value=vals.get(key)
        age=worker.snapshot_metrics().get('sample_age_ms')
        fresh=(age is not None and age <= 1500 and sample.get('status_verified') is True and
               (results.get(key) == 'ok' or isinstance(results.get(key),dict) and results[key].get('status') == 'ok'))
        connected=worker.connection_state=='Connected (read-only)'
        # A ready bit alone does not identify a position. A specific checkpoint
        # binding must be independently commissioned before real triggering.
        cp_key=p['checkpoint_variable'].upper()
        expected_checkpoint=str(r['recipe']['checkpoints'][view])
        actual_checkpoint=vals.get(cp_key)
        checkpoint_ok=(bool(cp_key) and cp_key in vals and str(actual_checkpoint)==expected_checkpoint and
                       (results.get(cp_key)=='ok' or isinstance(results.get(cp_key),dict) and results[cp_key].get('status')=='ok'))
        rising=self._last_bit is not None and str(self._last_bit)!=str(p['required_ready_value']) and str(value)==str(p['required_ready_value'])
        ok,why=apply_ready_gate(p['capture_mode'],robot_connected=connected,sample_fresh=fresh,
                                 value=value,required=p['required_ready_value'],
                                 checkpoint_ok=checkpoint_ok,rising_edge=rising)
        self._last_bit=value if fresh else None
        if ok:self.do_test('ROBOT_READY_SOFTWARE')
        elif connected:self.status.setText('ARMED / safety gated: '+why+'; checkpoint mapping requires hardware validation')

    def offline_test(self):
        try:
            _,_,p=self.selected()
            if p['capture_mode']!='ROBOT_READY_SOFTWARE':raise ValueError('Set view to Robot Ready mode first')
            self.do_test('OFFLINE_SYNTHETIC_READY_EVENT')
        except Exception as ex:QMessageBox.warning(self,'Offline test',str(ex))

    def disarm(self,keep_status=False):
        self._armed=False;self._last_bit=None
        if not keep_status:self.status.setText('Not armed')
