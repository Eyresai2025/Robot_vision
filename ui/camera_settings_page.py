"""SKU-aware, read-only until Save New Version; never writes a physical camera."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,
    QLineEdit,QComboBox,QPushButton,QMessageBox,QCheckBox,QScrollArea)
from core import sku_store as store
from core.camera_profiles import normalize_profile, profile_checks

PURPLE='#703AE7'


class CameraSettingsPage(QWidget):
    recipe_saved = Signal(str)
    def __init__(self):
        super().__init__()
        self.record=None
        self.current_view='sidewall1'
        self.profiles={}
        root=QVBoxLayout(self);root.setContentsMargins(24,20,24,20);root.setSpacing(12)
        title=QLabel('4K LUCID Camera Configuration');title.setStyleSheet('font-size:26px;font-weight:800;color:#211543')
        root.addWidget(title)
        root.addWidget(QLabel('SKU → five view-specific settings → save a new immutable recipe version. Software trigger only.'))
        row=QHBoxLayout();root.addLayout(row)
        row.addWidget(QLabel('Select SKU:'))
        self.sku=QComboBox();row.addWidget(self.sku,3)
        self.refresh_btn=QPushButton('Reload SKU List');row.addWidget(self.refresh_btn)
        row.addWidget(QLabel('Inspection View:'))
        self.view=QComboBox()
        for key in store.VIEWS:self.view.addItem(store.VIEW_NAMES[key],key)
        row.addWidget(self.view,2)
        self.details=QLabel('');self.details.setStyleSheet('color:#6739D5;font-weight:700');root.addWidget(self.details)
        self.warn=QLabel('');self.warn.setWordWrap(True);self.warn.setStyleSheet('color:#AD5B22');root.addWidget(self.warn)
        form=QFrame();form.setObjectName('stationCard');formlay=QVBoxLayout(form)
        grid=QGridLayout();grid.setSpacing(12);formlay.addLayout(grid)
        self.inputs={}
        names=[('Exposure (µs)','exposure_us'),('Gain (dB)','gain_db'),
            ('Image height (lines)','frame_lines'),('Internal line rate (Hz)','line_rate_hz'),
            ('Capture timeout (ms)','image_timeout_ms'),('Readiness timeout (ms)','readiness_timeout_ms'),
            ('Camera serial / binding','camera_serial'),('Ready variable (B/I)','ready_variable'),
            ('Checkpoint variable (B/I)','checkpoint_variable'),
            ('FFC gain minimum','ffc_gain_min'),('FFC gain maximum','ffc_gain_max'),
            ('FFC row block','ffc_row_block'),('Illumination ID','illumination_profile')]
        for i,(display,key) in enumerate(names):
            cell=QVBoxLayout();cell.addWidget(QLabel(display));edit=QLineEdit();cell.addWidget(edit)
            self.inputs[key]=edit;grid.addLayout(cell,i//2,i%2)
        for labeltext,key,entries in [
            ('Capture trigger mode','capture_mode',[('Manual → software start','MANUAL_SOFTWARE'),('Robot ready bit → software start','ROBOT_READY_SOFTWARE')]),
            ('Software selector','start_selector',[('AcquisitionStart','AcquisitionStart'),('FrameStart (verify support)','FrameStart')]),
            ('Flat-field correction','ffc_mode',[('Off','OFF'),('Software FFC (no reference)','SOFTWARE'),('Camera calibrated (separate calibration)','CAMERA_CALIBRATED')])]:
            row2=QHBoxLayout();row2.addWidget(QLabel(labeltext));cb=QComboBox()
            for display,val in entries:cb.addItem(display,val)
            self.inputs[key]=cb;row2.addWidget(cb,1);formlay.addLayout(row2)
        for labeltext,key,entries in [
            ('FFC target','ffc_target_mode',[('95th percentile','PERCENTILE_95'),('Maximum','MAX'),('Mean','MEAN')]),
            ('FFC failure handling','ffc_fail_policy',[('Fail capture if FFC fails','raise'),('Keep raw and report error','raw')])]:
            ffrow=QHBoxLayout();ffrow.addWidget(QLabel(labeltext));cb=QComboBox()
            for display,val in entries:cb.addItem(display,val)
            self.inputs[key]=cb;ffrow.addWidget(cb,1);formlay.addLayout(ffrow)
        form_l=QLabel('FFC: compute column gains from each stitched image; no external reference image. '
                      'Defaults: PERCENTILE_95, gain 1.0–15.99, 512-row blocks. '
                      'Camera-side FFC is a separate commissioning workflow.')
        form_l.setWordWrap(True);formlay.addWidget(form_l)
        root.addWidget(form)
        root.addWidget(QLabel('Internal line timing is camera-generated; no encoder or external LineStart configured.'))
        self.approval=QCheckBox('Create a NEW DRAFT version (never overwrite or automatically activate an existing recipe)')
        root.addWidget(self.approval)
        action=QHBoxLayout();root.addLayout(action)
        self.check=QPushButton('Validate View');action.addWidget(self.check)
        self.save=QPushButton('Save Camera Settings as New Draft');self.save.setObjectName('primary');action.addWidget(self.save)
        root.addStretch()
        self.sku.currentIndexChanged.connect(self.on_sku)
        self.view.currentIndexChanged.connect(self.on_view)
        self.refresh_btn.clicked.connect(self.refresh)
        self.check.clicked.connect(self.validate_view)
        self.save.clicked.connect(self.persist)
        self.refresh()

    def refresh(self, selected=None):
        prior=selected or self.sku.currentData()
        self.sku.blockSignals(True);self.sku.clear()
        for row in store.list_skus():self.sku.addItem(f'{row[0]}  ·  V{row[4]}  ({row[5]})',row[0])
        idx=self.sku.findData(prior);self.sku.setCurrentIndex(idx if idx>=0 else (0 if self.sku.count() else -1))
        self.sku.blockSignals(False)
        self.on_sku()

    def on_sku(self,_=None):
        code=self.sku.currentData();self.record=store.get_recipe(code) if code else None
        self.profiles={v:normalize_profile(self.record['recipe']['camera_profiles'][v]) for v in store.VIEWS} if self.record else {}
        self.current_view=self.view.currentData() or 'sidewall1';self.load_view()

    def save_current(self):
        if not self.record or self.current_view not in self.profiles:return
        p=self.profiles[self.current_view]
        for key,widget in self.inputs.items():
            p[key]=str(widget.currentData()) if isinstance(widget,QComboBox) else widget.text().strip()
        p['trigger']='SOFTWARE_START';p['line_source']='INTERNAL_TIMED'

    def on_view(self,_=None):
        self.save_current()
        self.current_view=self.view.currentData() or 'sidewall1'
        self.load_view()

    def load_view(self):
        if not self.record:return
        p=self.profiles[self.current_view]
        for key,widget in self.inputs.items():
            if isinstance(widget,QComboBox):widget.setCurrentIndex(max(0,widget.findData(p[key])))
            else:widget.setText(str(p.get(key,'')))
        s,r,c=store.ASSIGNMENTS[self.current_view]
        self.details.setText(f'{s} · {r} · {c} · 4K Mono8 · Software start · SKU {self.record["sku"]} V{self.record["version"]}')
        self.warn.setText('SDK settings are NOT sent to a camera by this page. Hardware commissioning pending.')

    def validate_view(self):
        self.save_current()
        errors=profile_checks(self.profiles[self.current_view])
        QMessageBox.information(self,'Camera profile', '\n'.join(errors) if errors else 'Configuration checks passed. Hardware capability not yet verified.')

    def persist(self):
        if not self.record:return
        if not self.approval.isChecked():
            QMessageBox.warning(self,'Confirm draft','Confirm creation of a new draft recipe version.');return
        self.save_current()
        data=dict(self.record['recipe']);data['camera_profiles']=self.profiles
        try:result=store.save_recipe(data,'DRAFT')
        except Exception as ex:QMessageBox.warning(self,'Save failed',str(ex));return
        self.approval.setChecked(False);self.refresh(result['sku']);self.recipe_saved.emit(result['sku'])
        QMessageBox.information(self,'Saved',f'{result["sku"]} V{result["version"]} saved as DRAFT. Review and activate for simulation from New SKU Setup. camera_profile_v{result["version"]}.json exported.')
