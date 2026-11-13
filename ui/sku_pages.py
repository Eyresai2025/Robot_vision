"""SKU Management and seven-step wizard for EyRes QC+ Robot Vision.

All controls are configuration-only. Nothing here talks to PLCs, robots,
or real cameras. A SIM_ACTIVE recipe is a simulation setting, not an
approval for production or robot motion.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QLineEdit,
    QPushButton,QComboBox,QStackedWidget,QTextEdit,QCheckBox,QTableWidget,
    QTableWidgetItem,QHeaderView,QMessageBox,QSizePolicy,QAbstractItemView
)
from core import sku_store as store

PURPLE='#703AE7'; INK='#211543'; MUTED='#747B95'


def txt(value, size=12, color=INK, bold=False):
    w=QLabel(str(value));w.setWordWrap(True)
    w.setStyleSheet(f'color:{color};font-size:{size}px;'+('font-weight:800;' if bold else ''))
    return w


def button(title,primary=False):
    b=QPushButton(title);b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setObjectName('primary' if primary else 'secondary')
    b.setMinimumHeight(38)
    return b


def card(layout, title=None):
    frame=QFrame();frame.setObjectName('stationCard')
    v=QVBoxLayout(frame);v.setContentsMargins(20,17,20,20);v.setSpacing(13)
    if title: v.addWidget(txt(title,16,INK,True))
    layout.addWidget(frame)
    return v


def textbox(label, parent, default='', placeholder=''):
    parent.addWidget(txt(label,11,MUTED,True))
    edit=QLineEdit(str(default));edit.setPlaceholderText(placeholder)
    parent.addWidget(edit)
    return edit


class SKUManagement(QWidget):
    new_requested=Signal()
    edit_requested=Signal(str)
    changed=Signal()
    def __init__(self):
        super().__init__();self.setObjectName('page')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        v=QVBoxLayout(self);v.setContentsMargins(24,23,24,26);v.setSpacing(15)
        head=QHBoxLayout()
        header=QVBoxLayout();header.addWidget(txt('SKU Management',27,INK,True))
        header.addWidget(txt('Manage tyre configurations, recipe versions and simulation-ready profiles',12,MUTED))
        head.addLayout(header,1)
        new=button('+  New SKU',True);new.clicked.connect(self.new_requested.emit)
        head.addWidget(new,0,Qt.AlignmentFlag.AlignTop);v.addLayout(head)
        self.search=QLineEdit();self.search.setPlaceholderText('Search by SKU code or tyre specification...')
        self.search.textChanged.connect(self.filter);v.addWidget(self.search)
        content=card(v,'Saved SKU Recipes')
        self.table=QTableWidget(0,6)
        self.table.setHorizontalHeaderLabels(['SKU Code','Tyre Specification','Version','Status','Updated','Action'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setShowGrid(False);self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(300)
        self.table.cellDoubleClicked.connect(self.edit_row)
        content.addWidget(self.table)
        note=txt('Draft and Reviewed recipes are not available for Live Capture. Simulation Active recipes can be used only in virtual capture mode. Double-click a row to create its next version.',11,MUTED)
        content.addWidget(note)
        v.addStretch(1)
        self.refresh()

    def refresh(self):
        self.records=store.list_skus()
        self.table.setRowCount(len(self.records))
        for row,record in enumerate(self.records):
            code,width,aspect,rim,version,status,modified=record
            rimtext=str(int(rim)) if float(rim).is_integer() else str(rim)
            vals=(code,f'{width}/{aspect} R{rimtext}',f'V{version}',status.replace('_',' ').title(),modified[:19],'Edit / Revise')
            for col,val in enumerate(vals):
                item=QTableWidgetItem(str(val));self.table.setItem(row,col,item)
        self.filter(self.search.text())

    def filter(self, term):
        needle=term.strip().lower()
        for row in range(self.table.rowCount()):
            source=' '.join(self.table.item(row,col).text() for col in (0,1,3))
            self.table.setRowHidden(row,needle not in source.lower())

    def edit_row(self,row,_column):
        if 0<=row<len(self.records):self.edit_requested.emit(self.records[row][0])


class SKUWizard(QWidget):
    saved=Signal(str)
    def __init__(self):
        super().__init__();self.setObjectName('page')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground,True)
        self.data=store.initial_recipe();self.loaded_version=0
        self.views=list(store.VIEWS);self.current_view='sidewall1';self.current_step=0
        main=QVBoxLayout(self);main.setContentsMargins(24,23,24,28);main.setSpacing(14)
        main.addWidget(txt('New SKU Setup',27,INK,True))
        main.addWidget(txt('Seven-step recipe configuration · no robot motion or hardware writes',12,MUTED))
        banner=QHBoxLayout()
        self.sku_banner=txt('CEAT_195_65_R15',15,PURPLE,True)
        banner.addWidget(self.sku_banner);banner.addStretch()
        self.state=txt('Draft · Not production approved',11,MUTED,True);banner.addWidget(self.state)
        main.addLayout(banner)
        self.steps=['SKU Details','Station Assignment','Robot Positions','Camera Profiles','Capture Calibration','Validation','Save Recipe']
        step_row=QHBoxLayout();step_row.setSpacing(5)
        self.step_buttons=[]
        for i,name in enumerate(self.steps):
            b=button(f'{i+1}. {name}')
            b.setMinimumHeight(34);b.clicked.connect(lambda _=False,index=i:self.show_step(index))
            step_row.addWidget(b);self.step_buttons.append(b)
        main.addLayout(step_row)
        self.stack=QStackedWidget();main.addWidget(self.stack,1)
        for maker in (self.build_details,self.build_stations,self.build_positions,self.build_cameras,
                      self.build_calibration,self.build_validation,self.build_save):
            page=QWidget();layout=QVBoxLayout(page);layout.setContentsMargins(0,0,0,0);layout.setSpacing(10)
            maker(layout);layout.addStretch();self.stack.addWidget(page)
        foot=QHBoxLayout()
        self.prev=button('←  Previous');self.prev.clicked.connect(lambda:self.show_step(self.current_step-1))
        self.next=button('Next Step  →',True);self.next.clicked.connect(lambda:self.show_step(self.current_step+1))
        foot.addWidget(self.prev);foot.addStretch()
        foot.addWidget(self.next);main.addLayout(foot)
        self.show_step(0)

    def build_details(self,v):
        p=card(v,'Step 1 — Tyre Specification')
        self.code=textbox('SKU Code',p,'CEAT_195_65_R15')
        grid=QGridLayout();grid.setSpacing(12)
        fields=[]
        for name,default in [('Width (mm)','195'),('Aspect ratio (%)','65'),('Rim (inches)','15')]:
            col=QVBoxLayout();fields.append(textbox(name,col,default))
            grid.addLayout(col,0,len(fields)-1)
        self.width,self.aspect,self.rim=fields;p.addLayout(grid)
        self.rpm=textbox('Nominal capture RPM',p,'60')
        self.description=textbox('Description / notes',p,'')
        p.addWidget(txt('Actual spindle speed, encoder settings and production capture settings must be verified during commissioning.',11,MUTED))

    def build_stations(self,v):
        p=card(v,'Step 2 — Station Assignment')
        p.addWidget(txt('Fixed five-view layout for the dual-robot inspection cell.',12,MUTED))
        grid=QGridLayout();grid.setSpacing(15)
        for col,(title,subtitle,entries) in enumerate((
            ('Station 01 · Robot 1','Camera 1 · 4K robot-mounted line scan',['Sidewall 1','Inner Side']),
            ('Station 02 · Robot 2','Camera 2 · 4K robot-mounted line scan',['Tread','Bead','Sidewall 2'])
        )):
            frame=QFrame();frame.setObjectName('noteInfo')
            f=QVBoxLayout(frame);f.setContentsMargins(17,18,17,18);f.setSpacing(12)
            f.addWidget(txt(title,17,INK,True));f.addWidget(txt(subtitle,11,MUTED))
            for entry in entries:f.addWidget(txt('✓   '+entry,13,PURPLE,True))
            grid.addWidget(frame,0,col)
        p.addLayout(grid)
        self.confirm_station=QCheckBox('Confirm proposed five-view station assignment')
        self.confirm_station.setChecked(True);p.addWidget(self.confirm_station)

    def build_positions(self,v):
        p=card(v,'Step 3 — Robot Position Mapping')
        p.addWidget(txt('Proposed checkpoint IDs only; not actual taught robot coordinates or job names.',12,MUTED))
        self.cp_fields={}
        grid=QGridLayout();grid.setSpacing(12)
        for i,key in enumerate(self.views):
            field=QVBoxLayout();field.addWidget(txt(store.VIEW_NAMES[key]+' · '+store.ASSIGNMENTS[key][1],11,MUTED,True))
            edit=QLineEdit(store.DEFAULT_CP[key]);field.addWidget(edit)
            self.cp_fields[key]=edit;grid.addLayout(field,i//2,i%2)
        p.addLayout(grid)
        p.addWidget(txt('Any physical job mapping must be verified with Yaskawa and the controls engineer before hardware writes are permitted.',11,MUTED))

    def build_cameras(self,v):
        p=card(v,'Step 4 — Software-Start Camera Profiles')
        p.addWidget(txt('Two shared 4K LUCID cameras. Each of the five views has independent settings. No encoder or hardware trigger.',12,MUTED))
        self.view_picker=QComboBox()
        for key in self.views:self.view_picker.addItem(store.VIEW_NAMES[key],key)
        p.addWidget(self.view_picker)
        self.assignment=txt('',12,PURPLE,True);p.addWidget(self.assignment)
        grid=QGridLayout();grid.setSpacing(11)
        labels=[('Exposure (µs)','exposure_us','Measured value'),('Gain (dB)','gain_db','0'),
                ('Capture lines / image height','frame_lines','Required line count'),
                ('Internal line rate (Hz)','line_rate_hz','Camera-specific line rate'),
                ('Image timeout (ms)','image_timeout_ms','15000'),
                ('Ready timeout (ms)','readiness_timeout_ms','5000'),
                ('Approved ready B/I variable','ready_variable','For robot-ready mode only'),
                ('Approved checkpoint B/I variable','checkpoint_variable','e.g. I011'),
                ('Camera serial (optional)','camera_serial','Bind on commissioning'),
                ('FFC gain minimum','ffc_gain_min','default 1.0'),
                ('FFC gain maximum','ffc_gain_max','default 15.99'),
                ('FFC row block','ffc_row_block','default 512'),
                ('Illumination profile','illumination_profile','Optional approved lighting ID')]
        self.camera_fields={}
        for i,(heading,key,hint) in enumerate(labels):
            cell=QVBoxLayout();cell.addWidget(txt(heading,11,MUTED,True));edit=QLineEdit()
            edit.setPlaceholderText(hint);cell.addWidget(edit);grid.addLayout(cell,i//2,i%2)
            self.camera_fields[key]=edit
        p.addLayout(grid)
        modes=QHBoxLayout()
        for title, attr, options in (
            ('Capture start mode','capture_mode', [('Manual software capture','MANUAL_SOFTWARE'),('Robot ready bit → software capture','ROBOT_READY_SOFTWARE')]),
            ('Software start selector','start_selector',[('AcquisitionStart','AcquisitionStart'),('FrameStart (if supported)','FrameStart')]),
            ('Flat-field correction','ffc_mode',[('Off','OFF'),('Software FFC (no reference)','SOFTWARE'),('Camera calibrated (separate)','CAMERA_CALIBRATED')])):
            box=QVBoxLayout();box.addWidget(txt(title,11,MUTED,True));cb=QComboBox()
            for display,code in options:cb.addItem(display,code)
            setattr(self,attr,cb);box.addWidget(cb);modes.addLayout(box)
        p.addLayout(modes)
        ffrow=QHBoxLayout()
        for title, attr, options in (
            ('FFC target','ffc_target_mode',[('95th percentile','PERCENTILE_95'),('Maximum','MAX'),('Mean','MEAN')]),
            ('FFC failure handling','ffc_fail_policy',[('Fail capture','raise'),('Retain raw + report','raw')])):
            box=QVBoxLayout();box.addWidget(txt(title,11,MUTED,True));cb=QComboBox()
            for display,code in options:cb.addItem(display,code)
            setattr(self,attr,cb);box.addWidget(cb);ffrow.addLayout(box)
        p.addLayout(ffrow)
        p.addWidget(txt('software FFC computes one gain per column from each stitched image; '
                        'no reference-image path is needed. Default 95th percentile, gain 1.0–15.99, '
                        '512-row blocks.',11,MUTED))
        self.trigger=self.capture_mode # keep V8 UI references safe; no encoder selection
        p.addWidget(txt('Line generation: INTERNAL TIMED (software starts an acquisition; it does not generate every line). '
                        'Hardware capabilities and achievable line rate require physical camera verification.',11,MUTED))
        self.view_picker.currentIndexChanged.connect(self.on_view_changed)
        self.render_camera()

    def build_calibration(self,v):
        p=card(v,'Step 5 — Capture Calibration')
        p.addWidget(txt('Virtual capture images are simulated patterns. No physical camera calibration is performed here.',12,MUTED))
        r=QHBoxLayout()
        for title,desc in (('Camera 1 Preview','Sidewall 1 / Inner Side'),('Camera 2 Preview','Tread / Bead / Sidewall 2')):
            box=QFrame();box.setObjectName('noteInfo');q=QVBoxLayout(box)
            q.setContentsMargins(20,25,20,25)
            q.addWidget(txt('▧',32,PURPLE,True),0,Qt.AlignmentFlag.AlignHCenter)
            q.addWidget(txt(title,14,INK,True),0,Qt.AlignmentFlag.AlignHCenter)
            q.addWidget(txt(desc,11,MUTED),0,Qt.AlignmentFlag.AlignHCenter)
            r.addWidget(box)
        p.addLayout(r)
        self.calibration=QCheckBox('I reviewed the simulated calibration workflow (NOT a physical calibration)')
        p.addWidget(self.calibration)
        p.addWidget(txt('Real qualification will require image inspection, line completeness, software-start and internal line-rate validation.',11,MUTED))

    def build_validation(self,v):
        p=card(v,'Step 6 — Recipe Validation')
        self.check_summary=txt('Configuration checks',13,PURPLE,True);p.addWidget(self.check_summary)
        self.check_table=QTableWidget(0,3)
        self.check_table.setHorizontalHeaderLabels(['Check','Status','Details'])
        self.check_table.verticalHeader().setVisible(False)
        self.check_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.check_table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents)
        self.check_table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        self.check_table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Stretch)
        self.check_table.verticalHeader().setDefaultSectionSize(40)
        self.check_table.setMinimumHeight(335);p.addWidget(self.check_table)
        p.addWidget(txt('Passing the simulator checks never certifies the actual Yaskawa robots, camera timing or production safety.',11,MUTED))

    def build_save(self,v):
        p=card(v,'Step 7 — Save and Review Recipe')
        self.summary=txt('',13,INK);p.addWidget(self.summary)
        self.reviewed=QCheckBox('I have reviewed the draft recipe details')
        self.reviewed.toggled.connect(lambda _checked:self.render_summary() if self.current_step==6 else None)
        p.addWidget(self.reviewed)
        r=QHBoxLayout()
        self.draft_button=button('Save Draft',True)
        self.draft_button.clicked.connect(lambda:self.persist('DRAFT'))
        self.review_button=button('Save as Reviewed')
        self.review_button.clicked.connect(lambda:self.persist('REVIEWED'))
        self.activate_button=button('Activate for Simulation')
        self.activate_button.clicked.connect(lambda:self.persist('SIM_ACTIVE'))
        for b in (self.draft_button,self.review_button,self.activate_button):r.addWidget(b)
        p.addLayout(r)
        p.addWidget(txt('Every Save creates a new immutable recipe version. Simulation activation makes it selectable on Live Capture only and NEVER permits robot movement.',11,MUTED))
        self.saved_info=txt('',12,PURPLE,True);p.addWidget(self.saved_info)

    def collect(self,strict=False):
        self.save_camera()
        data={'code':self.code.text(),'width':self.width.text(),'aspect':self.aspect.text(),
              'rim':self.rim.text(),'rpm':self.rpm.text(),'description':self.description.text(),
              'station_confirmed':self.confirm_station.isChecked(),
              'checkpoints':{key:ed.text() for key,ed in self.cp_fields.items()},
              'camera_profiles':self.data['camera_profiles'],
              'calibration_reviewed':self.calibration.isChecked()}
        if strict:return store.normalize(data)
        return data

    def save_camera(self):
        if not hasattr(self,'camera_fields'):return
        profile=dict(self.data['camera_profiles'].get(self.current_view,{}))
        profile.update({k:w.text() for k,w in self.camera_fields.items()})
        for key in ('capture_mode','start_selector','ffc_mode','ffc_target_mode','ffc_fail_policy'):
            profile[key]=getattr(self,key).currentData()
        profile['trigger']='SOFTWARE_START'
        profile['line_source']='INTERNAL_TIMED'
        self.data['camera_profiles'][self.current_view]=profile

    def on_view_changed(self,_index):
        self.save_camera()
        self.current_view=self.view_picker.currentData()
        self.render_camera()

    def render_camera(self):
        if not hasattr(self,'camera_fields'):return
        from core.camera_profiles import normalize_profile
        profile=normalize_profile(self.data['camera_profiles'][self.current_view])
        for key,w in self.camera_fields.items():w.setText(str(profile.get(key,'')))
        for key in ('capture_mode','start_selector','ffc_mode','ffc_target_mode','ffc_fail_policy'):
            cb=getattr(self,key);idx=cb.findData(profile[key]);cb.setCurrentIndex(max(0,idx))
        station,robot,camera=store.ASSIGNMENTS[self.current_view]
        self.assignment.setText(f'{station}  •  {robot}  •  {camera}  •  4096 px  •  SOFTWARE START')

    def populate(self, data,version=0):
        self.data=store.normalize(data);self.loaded_version=version
        for field,key in ((self.code,'code'),(self.width,'width'),(self.aspect,'aspect'),
                          (self.rim,'rim'),(self.rpm,'rpm'),(self.description,'description')):
            field.setText(str(self.data[key]))
        self.confirm_station.setChecked(self.data['station_confirmed'])
        for key,inp in self.cp_fields.items():inp.setText(self.data['checkpoints'][key])
        self.calibration.setChecked(self.data['calibration_reviewed'])
        self.view_picker.blockSignals(True);self.view_picker.setCurrentIndex(0);self.view_picker.blockSignals(False)
        self.current_view='sidewall1';self.render_camera();self.reviewed.setChecked(False)
        self.saved_info.setText('');self.show_step(0)

    def show_step(self,index):
        if not 0<=index<7:return
        self.save_camera()
        self.current_step=index;self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.step_buttons):
            b.setObjectName('primary' if i==index else 'secondary')
            b.style().unpolish(b);b.style().polish(b)
        self.prev.setEnabled(index>0)
        self.next.setVisible(index<6)
        self.sku_banner.setText(self.code.text().strip() or 'New SKU')
        self.state.setText(f'Draft · proposed V{self.loaded_version+1} · Simulation only')
        if index==5:self.render_validation()
        if index==6:self.render_summary()

    def render_validation(self):
        try:checks=store.validation(self.collect())
        except ValueError as ex:
            self.check_summary.setText('Specification issue: '+str(ex));return
        self.check_summary.setText(f'{sum(ok for _,ok,_ in checks)}/{len(checks)} checks ready · Hardware approval remains pending')
        self.check_table.setRowCount(len(checks))
        for i,(name,ok,detail) in enumerate(checks):
            for j,value in enumerate((name,'✓ Ready' if ok else '— Pending',detail)):
                self.check_table.setItem(i,j,QTableWidgetItem(str(value)))

    def render_summary(self):
        d=self.collect()
        self.summary.setText(f"SKU: {d['code']}   ·   Tyre: {d['width']}/{d['aspect']} R{d['rim']}   ·   "
                             f"RPM: {d['rpm']}\n5 inspection views  ·  2 robot stations  ·  "
                             f"Next version: V{self.loaded_version+1}  ·  No hardware authorization")
        self.review_button.setEnabled(self.reviewed.isChecked())
        try: self.activate_button.setEnabled(self.reviewed.isChecked() and all(ok for _,ok,_ in store.validation(d)[:5]))
        except ValueError:self.activate_button.setEnabled(False)

    def persist(self,status):
        if status!='DRAFT' and not self.reviewed.isChecked():
            QMessageBox.warning(self,'Review required','Check the recipe review acknowledgement first.');return
        try:
            result=store.save_recipe(self.collect(strict=True),status)
        except Exception as exc:
            QMessageBox.warning(self,'Cannot save SKU',str(exc));return
        self.loaded_version=result['version'];self.saved_info.setText(
            f"Saved {result['sku']} V{result['version']} — {status.replace('_',' ')} (simulation only)")
        self.saved.emit(result['sku']);self.show_step(6)
        QMessageBox.information(self,'Recipe saved',self.saved_info.text())
