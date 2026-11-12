"""Professional white-theme EyRes QC+ Robot Vision GUI.

Phase 1 continues using the original virtual robots, virtual 4K line-scan
frames, SQLite records, and manifest files. This module cannot command robots.
"""
from pathlib import Path
from datetime import datetime
import csv

from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QPixmap, QDesktopServices, QColor, QFont, QIcon, QPalette
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QPushButton, QLineEdit, QComboBox,
    QStackedWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QGridLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QProgressBar, QListView,
    QMessageBox, QAbstractItemView, QDialog, QDialogButtonBox, QSizePolicy,
    QGraphicsDropShadowEffect, QFileDialog
)

from core.simulator import Simulation
from core.robot_telemetry import VirtualRobot, load_addresses, save_addresses
from core.ymconnect_process import HardwareRobot, load_hardware_settings
from core.store import get_cycles, CAPTURES
from core import sku_store
from .sku_pages import SKUManagement, SKUWizard
from .theme import QSS, INK, MUTED, PURPLE, BLUE, MAGENTA, BORDER, WaveBanner, HeroPanel

BASE = Path(__file__).resolve().parents[1]
VIEWS = {
    'S1': [('sidewall1', 'Sidewall 1'), ('inner', 'Inner Side')],
    'S2': [('tread', 'Tread'), ('bead', 'Bead'), ('sidewall2', 'Sidewall 2')]
}
NAV = [
    ('Live Capture', 'camera'), ('Robot Monitor', 'robot'),
    ('Camera Settings', 'settings'), ('Station Mapping', 'network'),
    ('SKU Management', 'layers'), ('New SKU Setup', 'file'),
    ('Capture History', 'history'), ('System Diagnostics', 'activity')
]


def label(text, role='', size=None, color=None, bold=False, wrap=True):
    w = QLabel(str(text))
    if role:
        w.setObjectName(role)
    if size or color or bold:
        bits = []
        if size:
            bits.append(f'font-size:{size}px')
        if color:
            bits.append(f'color:{color}')
        if bold:
            bits.append('font-weight:800')
        w.setStyleSheet(';'.join(bits))
    w.setWordWrap(wrap)
    return w


def btn(text, kind='secondary'):
    w = QPushButton(text)
    w.setObjectName(kind)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    w.setMinimumHeight(38)
    return w


def layout_v(widget, margins=(18, 17, 18, 17), spacing=11):
    v = QVBoxLayout(widget)
    v.setContentsMargins(*margins)
    v.setSpacing(spacing)
    return v


def surface(parent=None, kind='surface', padding=(18, 17, 18, 17), spacing=11):
    w = QFrame(parent)
    w.setObjectName(kind)
    v = layout_v(w, padding, spacing)
    return w, v


ICON_ALIASES = {'♧':'robot','▧':'camera','◇':'layers','✓':'check','▤':'database',
                '▥':'server','⚙':'settings','◷':'history','▣':'camera'}


def icon_pixmap(name, color='purple', size=48):
    name = ICON_ALIASES.get(name, name)
    path = BASE / 'assets' / 'icons' / f'{name}_{color}.png'
    pix = QPixmap(str(path))
    if pix.isNull():
        return QPixmap()
    return pix.scaled(QSize(size,size), Qt.AspectRatioMode.KeepAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)


def icon_tile(symbol, kind='iconPurple', dimension=42, font_size=23):
    tile = QFrame()
    tile.setObjectName(kind)
    tile.setFixedSize(dimension, dimension)
    lay = QVBoxLayout(tile)
    lay.setContentsMargins(0, 0, 0, 0)
    glyph = QLabel()
    glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
    color = 'blue' if kind == 'iconBlue' else 'green' if kind == 'iconGreen' else 'purple'
    glyph.setPixmap(icon_pixmap(symbol, color, int(dimension*.56)))
    lay.addWidget(glyph)
    return tile


def set_button_icon(button, name, color='purple', size=16):
    button.setIcon(QIcon(icon_pixmap(name, color, size*2)))
    button.setIconSize(QSize(size, size))
    return button


def chip(text, kind='chipPurple'):
    w = label(text, role=kind, wrap=False)
    w.setAlignment(Qt.AlignmentFlag.AlignCenter)
    w.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    return w


def field_pair(parent_layout, caption, value):
    r = QHBoxLayout()
    r.setSpacing(16)
    r.addWidget(label(caption, 'muted'))
    r.addStretch()
    w = label(value, color=INK, bold=True)
    w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    r.addWidget(w)
    parent_layout.addLayout(r)
    return w


def table_config(t, row_height=39):
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setAlternatingRowColors(True)
    t.setShowGrid(False)
    t.verticalHeader().setVisible(False)
    t.verticalHeader().setDefaultSectionSize(row_height)
    t.horizontalHeader().setMinimumHeight(42)
    t.setWordWrap(False)


def table_item(value, alignment=None):
    x = QTableWidgetItem(str(value))
    if alignment:
        x.setTextAlignment(alignment)
    return x


class FramePreview(QDialog):
    """Simple full-image viewer for simulated or captured local frames."""
    def __init__(self, title, file_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'{title} — Image Preview')
        self.resize(900, 600)
        self.setStyleSheet('QDialog { background:#F8F8FF; } QLabel { color:#15113C; }')
        v = QVBoxLayout(self)
        v.setContentsMargins(15, 15, 15, 15)
        v.setSpacing(10)
        v.addWidget(label(title, size=18, bold=True))
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        picture = QLabel()
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img = QPixmap(str(file_path))
        if not img.isNull():
            picture.setPixmap(img.scaled(QSize(820, 465), Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        else:
            picture.setText('Image not available')
        area.setWidget(picture)
        v.addWidget(area, 1)
        v.addWidget(label(str(file_path), size=11, color=MUTED))
        close = btn('Close')
        close.clicked.connect(self.accept)
        v.addWidget(close, 0, Qt.AlignmentFlag.AlignRight)


class CaptureTile(QFrame):
    def __init__(self, view, display, parent=None):
        super().__init__(parent)
        self.view = view
        self.display = display
        self.image_path = None
        self.setObjectName('captureTile')
        self.setMinimumWidth(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        v = layout_v(self, (9, 9, 9, 10), 6)
        self.thumbnail = QLabel()
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setPixmap(icon_pixmap('camera','gray',32))
        self.thumbnail.setMinimumHeight(100)
        self.thumbnail.setStyleSheet('background:#F0F0FA;border-radius:8px;color:#AEACCC;font-size:32px;')
        self.thumbnail.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        v.addWidget(self.thumbnail)
        v.addWidget(label(display, size=13, color=INK, bold=True))
        self.status = label('○ Pending', color=MUTED, size=11)
        v.addWidget(self.status)
        self.note = label('Waiting for checkpoint', color='#8A92A9', size=10)
        v.addWidget(self.note)
        self.open_button = btn('View image')
        self.open_button.setMinimumHeight(28)
        self.open_button.setStyleSheet('QPushButton {background:#F5F0FF;border:0;border-radius:7px;color:#6332C9;font-size:11px;font-weight:750;padding:5px;} QPushButton:disabled {background:#F5F5FA;color:#A3A2B4;}')
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_preview)
        v.addWidget(self.open_button)

    def reset(self):
        self.image_path = None
        self.thumbnail.setPixmap(QPixmap())
        self.thumbnail.setPixmap(icon_pixmap('camera','gray',32))
        self.status.setText('○ Pending')
        self.status.setStyleSheet(f'color:{MUTED};font-size:11px;')
        self.note.setText('Waiting for checkpoint')
        self.open_button.setEnabled(False)

    def capturing(self):
        self.status.setText('● Acquiring image')
        self.status.setStyleSheet('color:#6C3EE3;font-size:11px;font-weight:700;')
        self.note.setText('Virtual encoder running')

    def complete(self, path):
        self.image_path = Path(path)
        pixmap = QPixmap(str(path))
        if not pixmap.isNull():
            target = QSize(max(self.thumbnail.width(), 160), 100)
            self.thumbnail.setText('')
            self.thumbnail.setPixmap(pixmap.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                  Qt.TransformationMode.SmoothTransformation))
        self.status.setText('✓ Simulated frame saved')
        self.status.setStyleSheet('color:#148753;font-size:11px;font-weight:750;')
        self.note.setText('Saved and verified')
        self.open_button.setEnabled(True)

    def open_preview(self):
        if self.image_path is not None and self.image_path.exists():
            FramePreview(self.display, self.image_path, self).exec()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('EyRes QC+ Robot Vision — SIMULATION')
        self.setWindowIcon(QIcon(str(BASE / 'assets' / 'eyres_symbol.png')))
        self.setStyleSheet(QSS)
        self.resize(1600, 940)
        self.setMinimumSize(1130, 720)
        self.sim = Simulation()
        self.sim.started.connect(self.on_started)
        self.sim.progress.connect(self.on_progress)
        self.sim.finished.connect(self.on_finished)
        self.sim.log.connect(self.log_event)
        self.telemetry = {i: VirtualRobot(i, self) for i in (1, 2)}
        self.hardware_robots = {i: HardwareRobot(i, self) for i in (1, 2)}
        self.robot_addresses = load_addresses()
        self.telemetry_logs = []
        self.nav_buttons = {}
        self.page_ids = {}
        self.tiles = {}
        self.station_status = {}
        self._build_shell()
        for controller in self.telemetry.values():
            controller.updated.connect(self.update_telemetry)
            controller.note.connect(self.telemetry_note)
            controller.connect_virtual()
        for rid, device in self.hardware_robots.items():
            device.state.connect(self.on_hardware_state)
            device.sample.connect(self.on_hardware_sample)
            device.note.connect(self.telemetry_note)
        self.navigate('Live Capture')
        self.refresh_skus()
        self.refresh_history()

    def _build_shell(self):
        root = QWidget()
        root.setObjectName('root')
        root.setAutoFillBackground(True)
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        side = QFrame()
        side.setObjectName('sidebar')
        side.setFixedWidth(244)
        h.addWidget(side)
        sv = QVBoxLayout(side)
        sv.setContentsMargins(13, 18, 13, 18)
        sv.setSpacing(6)

        brand = QVBoxLayout()
        brand.setSpacing(6)
        logo_label = QLabel()
        logo_label.setObjectName('companyLogo')
        logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        logo_label.setFixedHeight(72)
        logo_label.setFixedWidth(218)
        company = QPixmap(str(BASE / 'assets' / 'eyres_company_logo.png'))
        if not company.isNull():
            logo_label.setPixmap(company.scaled(QSize(210, 65),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        brand.addWidget(logo_label)
        sv.addLayout(brand)
        sv.addSpacing(19)

        for title, glyph in NAV:
            b = btn(title, 'nav')
            set_button_icon(b, glyph, 'nav', 21)
            b.setIconSize(QSize(21, 21))
            b.setMinimumHeight(45)
            b.clicked.connect(lambda checked=False, name=title: self.navigate(name))
            self.nav_buttons[title] = b
            sv.addWidget(b)
        sv.addStretch()
        footer, fv = surface(kind='noteInfo', padding=(12, 12, 12, 12), spacing=6)
        fv.addWidget(label('PHASE 1  ·  VIRTUAL DEVICES', size=10, color='#504178', bold=True))
        fv.addWidget(label('2 robots  |  2 cameras  |  5 views', size=10, color='#687196'))
        sv.addWidget(footer)

        body = QWidget()
        body.setObjectName('body')
        body.setAutoFillBackground(True)
        h.addWidget(body, 1)
        bv = QVBoxLayout(body)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)

        top = QFrame()
        top.setObjectName('topBar')
        top.setFixedHeight(69)
        th = QHBoxLayout(top)
        th.setContentsMargins(23, 10, 25, 10)
        th.setSpacing(15)
        client = QLabel()
        client.setObjectName('clientLogo')
        client.setAlignment(Qt.AlignmentFlag.AlignCenter)
        client.setFixedSize(111, 46)
        ceat = QPixmap(str(BASE / 'assets' / 'ceat_client_logo.png'))
        if not ceat.isNull():
            client.setPixmap(ceat.scaled(QSize(94, 35),
                     Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation))
        th.addWidget(client)
        divider = QFrame()
        divider.setObjectName('separator')
        divider.setFixedSize(1, 26)
        th.addWidget(divider)
        th.addWidget(label('DUAL-ROBOT INSPECTION CELL', size=12, color=INK, bold=True))
        th.addStretch()
        th.addWidget(chip('●  SIMULATION MODE', 'chipPurple'))
        bv.addWidget(top)
        self.stack = QStackedWidget()
        self.stack.setObjectName('pageStack')
        self.stack.setAutoFillBackground(True)
        bv.addWidget(self.stack, 1)

        factories = [
            ('Live Capture', self.build_live),
            ('Robot Monitor', self.build_robot_monitor),
            ('Camera Settings', self.build_cameras),
            ('Station Mapping', self.build_mapping),
            ('SKU Management', self.build_sku_management),
            ('New SKU Setup', self.build_sku_wizard),
            ('Capture History', self.build_history),
            ('System Diagnostics', self.build_diagnostics)
        ]
        for name, builder in factories:
            content = builder()
            scroll = QScrollArea()
            scroll.setObjectName('pageScroll')
            scroll.setWidgetResizable(True)
            light = scroll.palette()
            light.setColor(QPalette.ColorRole.Window, QColor('#F7F8FF'))
            light.setColor(QPalette.ColorRole.Base, QColor('#F7F8FF'))
            scroll.setPalette(light)
            scroll.viewport().setPalette(light)
            scroll.viewport().setAutoFillBackground(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(content)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.page_ids[name] = self.stack.addWidget(scroll)

    def navigate(self, name):
        self.stack.setCurrentIndex(self.page_ids[name])
        for key, b in self.nav_buttons.items():
            b.setProperty('active', 'true' if name == key else 'false')
            b.style().unpolish(b)
            b.style().polish(b)
            b.update()
        if name == 'Capture History':
            self.refresh_history()
        if name == 'SKU Management' and hasattr(self, 'sku_manager'):
            self.sku_manager.refresh()

    def page(self, heading, subtitle):
        page = QWidget()
        page.setObjectName('page')
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        page.setAutoFillBackground(True)
        # Do not set a recursive QWidget transparent stylesheet here: it
        # overrides child card, console, input and button backgrounds on Windows.
        v = QVBoxLayout(page)
        v.setContentsMargins(24, 23, 24, 26)
        v.setSpacing(17)
        hero = HeroPanel()
        hv = QVBoxLayout(hero)
        hv.setContentsMargins(0, 4, 0, 8)
        hv.setSpacing(3)
        hv.addWidget(label(heading, 'heading'))
        hv.addWidget(label(subtitle, 'subtitle'))
        hv.addStretch()
        v.addWidget(hero)
        return page, v

    def build_live(self):
        page, v = self.page('Live Inspection Workspace',
                            'Dual-station tyre capture orchestration  •  five-zone tyre coverage  •  virtual encoder acquisition')
        stats = QGridLayout()
        stats.setSpacing(12)
        v.addLayout(stats)
        metrics = [
            ('robot', 'ROBOTS', '2 / 2 Virtual', 'metricPurple', 'iconPurple'),
            ('camera', 'CAMERAS', '2 / 2 Virtual', 'metricBlue', 'iconBlue'),
            ('layers', 'CELL MODE', 'Simulation', 'metricCard', 'iconPurple'),
            ('check', 'CAPTURE STATE', 'Idle', 'metricGreen', 'iconGreen'),
        ]
        for idx, (sym, title, value, kind, icon_kind) in enumerate(metrics):
            w, q = surface(kind=kind, padding=(14, 14, 14, 15), spacing=3)
            r = QHBoxLayout()
            r.addWidget(icon_tile(sym, icon_kind, 43, 22))
            tc = QVBoxLayout()
            tc.setSpacing(3)
            tc.addWidget(label(title, size=10, color=MUTED, bold=True))
            val = label(value, role='metricValue')
            tc.addWidget(val)
            r.addLayout(tc)
            r.addStretch()
            q.addLayout(r)
            stats.addWidget(w, 0, idx)
            if title == 'CAPTURE STATE':
                self.capture_state = val

        control, cv = surface(padding=(16, 15, 16, 15), spacing=8)
        v.addWidget(control)
        cr = QHBoxLayout()
        cr.setSpacing(12)
        cv.addLayout(cr)
        bc = QVBoxLayout()
        bc.setSpacing(5)
        bc.addWidget(label('Tyre Barcode', 'fieldLabel'))
        self.barcode = QLineEdit('CEAT000123')
        self.barcode.setPlaceholderText('Scan or enter tyre barcode')
        bc.addWidget(self.barcode)
        cr.addLayout(bc, 5)
        sc = QVBoxLayout()
        sc.setSpacing(5)
        sc.addWidget(label('Active SKU', 'fieldLabel'))
        self.sku = QComboBox()
        self.sku.addItem('Loading saved SKUs...', None)
        self.sku.setView(QListView(self.sku))
        self.sku.view().setStyleSheet('QListView { background-color:#FFFFFF; color:#17143C; border:1px solid #D8D4ED; outline:0; } QListView::item { padding:7px; min-height:26px; } QListView::item:selected { color:#2E1B75; background-color:#EEE7FF; }')
        sc.addWidget(self.sku)
        cr.addLayout(sc, 3)
        manage_sku = btn('+ New SKU', 'secondary')
        manage_sku.clicked.connect(self.new_sku)
        cr.addWidget(manage_sku, 0, Qt.AlignmentFlag.AlignBottom)
        self.start_button = btn('Start Cycle', 'primary')
        set_button_icon(self.start_button,'play','white',16)
        self.start_button.clicked.connect(self.start_cycle)
        cr.addWidget(self.start_button, 0, Qt.AlignmentFlag.AlignBottom)
        self.stop_button = btn('Stop Cycle', 'danger')
        set_button_icon(self.stop_button,'square','purple',15)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.sim.stop)
        cr.addWidget(self.stop_button, 0, Qt.AlignmentFlag.AlignBottom)

        stations = QGridLayout()
        stations.setSpacing(14)
        stations.setColumnStretch(0, 1)
        stations.setColumnStretch(1, 1)
        v.addLayout(stations)
        for idx, (station, title, camera) in enumerate([
            ('S1', 'Station 01 · Robot 1', 'Camera 1'),
            ('S2', 'Station 02 · Robot 2', 'Camera 2')
        ]):
            w, q = surface(kind='stationCard', padding=(15, 15, 15, 15), spacing=12)
            stations.addWidget(w, 0, idx)
            header = QHBoxLayout()
            header.setSpacing(9)
            header.addWidget(icon_tile('robot', 'iconPurple', 42, 22))
            title_col = QVBoxLayout()
            title_col.setSpacing(4)
            title_col.addWidget(label(title, 'section'))
            title_col.addWidget(label(f'4K LINE SCAN   •   ROBOT-MOUNTED   •   {camera.upper()}', size=10, color=MUTED))
            header.addLayout(title_col)
            header.addStretch()
            status = chip('●  WAITING', 'chipNeutral')
            self.station_status[station] = status
            header.addWidget(status)
            q.addLayout(header)
            grid = QGridLayout()
            grid.setHorizontalSpacing(9)
            grid.setVerticalSpacing(9)
            q.addLayout(grid)
            for col, (key, display) in enumerate(VIEWS[station]):
                tile = CaptureTile(key, display)
                grid.addWidget(tile, 0, col)
                grid.setColumnStretch(col, 1)
                self.tiles[key] = tile
            q.addStretch()

        progress_card, pc = surface(padding=(17, 13, 17, 15), spacing=10)
        v.addWidget(progress_card)
        r = QHBoxLayout()
        r.addWidget(icon_tile('layers', 'iconPurple', 36, 20))
        r.addWidget(label('Capture Progress', 'section'))
        r.addStretch()
        self.progress_text = label('0 / 5 images (0%)', size=12, color='#6535D6', bold=True)
        r.addWidget(self.progress_text)
        pc.addLayout(r)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 5)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        pc.addWidget(self.progress_bar)

        logs, lc = surface(padding=(17, 13, 17, 16), spacing=10)
        v.addWidget(logs)
        console_header = QHBoxLayout()
        console_header.addWidget(icon_tile('file','iconPurple',36))
        console_header.addWidget(label('Live Event Console', 'section'))
        console_header.addStretch()
        lc.addLayout(console_header)
        self.console = QTextEdit()
        self.console.setObjectName('console')
        self.console.setReadOnly(True)
        self.console.setFixedHeight(112)
        self.console.append('[SYSTEM] Phase 1 ready. Two virtual robots and two virtual cameras available.')
        self.console.append('[SYSTEM] SIMULATION ONLY — no physical robot or camera commands.')
        lc.addWidget(self.console)
        return page

    def build_sku_management(self):
        self.sku_manager = SKUManagement()
        self.sku_manager.new_requested.connect(self.new_sku)
        self.sku_manager.edit_requested.connect(self.edit_sku)
        return self.sku_manager

    def build_sku_wizard(self):
        self.sku_wizard = SKUWizard()
        self.sku_wizard.saved.connect(self.recipe_saved)
        return self.sku_wizard

    def new_sku(self):
        self.sku_wizard.populate(sku_store.initial_recipe())
        self.navigate('New SKU Setup')

    def edit_sku(self, code):
        record = sku_store.get_recipe(code)
        if record is None:
            QMessageBox.warning(self, 'SKU not found', code)
            return
        self.sku_wizard.populate(record['recipe'], record['version'])
        self.navigate('New SKU Setup')

    def recipe_saved(self, code):
        self.refresh_skus(select=code)
        self.sku_manager.refresh()

    def refresh_skus(self, select=None):
        if not hasattr(self, 'sku'):
            return
        current = select or self.sku.currentData()
        entries = sku_store.selectable_skus()
        self.sku.blockSignals(True)
        self.sku.clear()
        for code, display, version in entries:
            self.sku.addItem(display, (code, version))
        if current:
            existing = next((i for i in range(self.sku.count())
                             if self.sku.itemData(i) == current or
                             (isinstance(self.sku.itemData(i), tuple) and self.sku.itemData(i)[0] == current)), -1)
            if existing >= 0: self.sku.setCurrentIndex(existing)
        self.sku.blockSignals(False)
        self.start_button.setEnabled(bool(entries) and not self.sim.running)

    def build_robot_monitor(self):
        page, v = self.page('Robot Communication Center',
                            'Dual-controller connectivity, virtual handshake and polling diagnostics')
        mode_bar, mb = surface(kind='surface', padding=(16, 13, 16, 13), spacing=10)
        mode_row = QHBoxLayout()
        mode_row.addWidget(icon_tile('robot', 'iconPurple', 42))
        mode_row.addWidget(label('Communication mode', 'section'))
        mode_row.addStretch()
        self.robot_mode = QComboBox()
        self.robot_mode.addItems(['Simulation', 'Hardware read-only (YMConnect bridge)'])
        self.robot_mode.setFixedWidth(280)
        self.robot_mode.currentIndexChanged.connect(self.robot_mode_changed)
        mode_row.addWidget(self.robot_mode)
        mb.addLayout(mode_row)
        self.mode_notice = label('Simulation uses independent 50 ms virtual polls. Timings below are local scheduling intervals, not HSES latency.',
                                 color=MUTED, size=11)
        mb.addWidget(self.mode_notice)
        v.addWidget(mode_bar)

        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.robot_widgets = {}
        for robot_id in (1, 2):
            card, q = surface(kind='stationCard', padding=(17, 16, 17, 16), spacing=11)
            grid.addWidget(card, 0, robot_id - 1)
            top = QHBoxLayout()
            top.addWidget(icon_tile('robot', 'iconPurple' if robot_id == 1 else 'iconBlue'))
            top.addWidget(label(f'Robot {robot_id} · Controller', 'section'))
            top.addStretch()
            status = chip('●  VIRTUAL', 'chipGreen')
            top.addWidget(status)
            q.addLayout(top)
            iprow = QHBoxLayout()
            iprow.addWidget(label('Controller IP (saved for later)', color=MUTED, size=11))
            ip = QLineEdit(self.robot_addresses[robot_id])
            ip.setFixedWidth(180)
            iprow.addWidget(ip)
            q.addLayout(iprow)
            buttonrow = QHBoxLayout()
            connect = btn('Disconnect virtual', 'secondary')
            connect.clicked.connect(lambda checked=False, rid=robot_id: self.toggle_robot(rid))
            buttonrow.addWidget(connect)
            buttonrow.addStretch()
            q.addLayout(buttonrow)
            fields = {}
            for name in ('Connection', 'Controller model', 'Servo status', 'Active checkpoint',
                         'Heartbeat', 'Local poll mean / P95 / max'):
                fields[name] = field_pair(q, name, '—')
            self.robot_widgets[robot_id] = {'ip': ip, 'status': status, 'toggle': connect, 'fields': fields}
        v.addLayout(grid)

        strip = QHBoxLayout()
        strip.addWidget(label('Virtual Handshake Register Monitor', 'section'))
        strip.addStretch()
        save_btn = btn('Save IP settings', 'secondary')
        save_btn.clicked.connect(self.save_robot_ips)
        strip.addWidget(save_btn)
        export_btn = btn('Export diagnostics CSV', 'secondary')
        export_btn.clicked.connect(self.export_telemetry)
        strip.addWidget(export_btn)
        v.addLayout(strip)

        registers = [('B010','PC_READY','Application'), ('B013','CAPTURE_REQ','Robot'),
                     ('B011','CAPTURE_RESULT','Application'), ('B012','RESULT_VALID','Application'),
                     ('B014','CYCLE_DONE','Robot'), ('I010','HEARTBEAT','Application'),
                     ('I011','CHECKPOINT_ID','Robot'), ('I012','REQ_TOKEN','Robot'),
                     ('I013','RESULT_TOKEN','Application'), ('I014','ROBOT_ERROR','Robot')]
        card, q = surface(kind='surface', padding=(15, 13, 15, 13), spacing=8)
        self.register_table = QTableWidget(len(registers), 5)
        self.register_table.setHorizontalHeaderLabels(['Register', 'Signal', 'Proposed owner', 'Robot 1', 'Robot 2'])
        table_config(self.register_table, 32)
        self.register_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.reg_rows = {}
        for row,(reg,signal,owner) in enumerate(registers):
            self.reg_rows[reg] = row
            for col,value in enumerate((reg,signal,owner,'—','—')):
                self.register_table.setItem(row,col,table_item(value))
        self.register_table.setFixedHeight(373)
        q.addWidget(self.register_table)
        v.addWidget(card)

        card, q = surface(kind='surface', padding=(15, 12, 15, 12), spacing=7)
        q.addWidget(label('Communication Events', 'section'))
        self.telemetry_console = QTextEdit()
        self.telemetry_console.setObjectName('console')
        self.telemetry_console.setReadOnly(True)
        self.telemetry_console.setFixedHeight(84)
        q.addWidget(self.telemetry_console)
        v.addWidget(card)
        warning, wl = surface(kind='noteWarn', padding=(12, 10, 12, 10))
        wl.addWidget(label('ⓘ  Production reads require the official YMConnect .NET SDK, controls-team approval and an explicit hardware enable flag. No writes, servo or job/motion controls exist in this application.',
                           size=11, color='#A66619'))
        v.addWidget(warning)
        v.addStretch()
        return page

    def robot_mode_changed(self, index):
        hardware = bool(index)
        self.mode_notice.setText(
            'Hardware read-only: manual Connect only. Requires official YMConnect bridge and controls-team approval. These measurements are not camera trigger timing.'
            if hardware else
            'Simulation uses independent 50 ms virtual polls. Timings are local scheduling intervals, not HSES latency.')
        for robot_id, virtual in self.telemetry.items():
            if hardware:
                virtual.disconnect_virtual()
            else:
                self.hardware_robots[robot_id].disconnect_readonly()
                virtual.connect_virtual()
        self.update_all_robot_statuses()
        if hardware:
            for rid in (1, 2): self.on_hardware_state(rid, self.hardware_robots[rid].connection_state)

    def toggle_robot(self, robot_id):
        if self.robot_mode.currentIndex():
            device = self.hardware_robots[robot_id]
            if device.connection_state in ('Connected (read-only)', 'Connecting'):
                device.disconnect_readonly()
                return
            try:
                settings = load_hardware_settings()
                if not settings['enabled']:
                    raise RuntimeError('Hardware access is disabled. Obtain controls-team approval and configure the YMConnect bridge first.')
                device.connect_readonly(self.robot_widgets[robot_id]['ip'].text().strip())
                self.telemetry_note(robot_id, 'Opening READ-ONLY YMConnect monitoring session; no command functionality.')
            except Exception as exc:
                QMessageBox.warning(self, 'Read-only connection unavailable', str(exc))
            return
        virtual = self.telemetry[robot_id]
        if virtual.connected: virtual.disconnect_virtual()
        else: virtual.connect_virtual()

    def on_hardware_state(self, robot_id, state):
        if not hasattr(self, 'robot_widgets') or robot_id not in self.robot_widgets or not self.robot_mode.currentIndex():
            return
        card = self.robot_widgets[robot_id]
        live = state == 'Connected (read-only)'
        card['status'].setText('●  REAL READ-ONLY' if live else '●  ' + state.upper())
        card['toggle'].setEnabled(True)
        card['toggle'].setText('Disconnect (read-only)' if state in ('Connecting','Connected (read-only)') else 'Connect (read-only)')
        card['fields']['Connection'].setText(state)
        card['fields']['Controller model'].setText('Not verified; robot arm GP8' if robot_id == 1 else 'Not verified; robot arm GP12')
        if not live:
            card['fields']['Servo status'].setText('Unknown')
            card['fields']['Active checkpoint'].setText('—')
            card['fields']['Heartbeat'].setText('—')
            card['fields']['Local poll mean / P95 / max'].setText('—')
            for reg in self.reg_rows:
                self.register_table.item(self.reg_rows[reg],robot_id+2).setText('—')

    def on_hardware_sample(self, robot_id, data):
        if not self.robot_mode.currentIndex(): return
        card = self.robot_widgets[robot_id]
        card['fields']['Local poll mean / P95 / max'].setText(f"Latest SDK read: {data.get('elapsed_ms', '—')} ms")
        card['fields']['Heartbeat'].setText('Physical heartbeat: not mapped')
        card['fields']['Servo status'].setText('Not available' if not data.get('status_read_supported') else str(data.get('status') or 'Read returned no decoded state'))
        for reg, value in (data.get('variables') or {}).items():
            if reg in self.reg_rows:
                self.register_table.item(self.reg_rows[reg], robot_id+2).setText('—' if value is None else str(value))

    def save_robot_ips(self):
        addresses = {i: self.robot_widgets[i]['ip'].text().strip() for i in (1,2)}
        try:
            save_addresses(addresses)
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, 'Invalid IP settings', str(exc))
            return
        self.robot_addresses = addresses
        self.telemetry_note(0, 'IP address configuration saved (no network connection opened).')

    def update_all_robot_statuses(self):
        for robot_id, virtual in self.telemetry.items():
            self.update_telemetry(robot_id, virtual.snapshot())

    def update_telemetry(self, robot_id, snapshot):
        if hasattr(self, "robot_mode") and self.robot_mode.currentIndex():
            return
        if not hasattr(self, 'robot_widgets') or robot_id not in self.robot_widgets:
            return
        card = self.robot_widgets[robot_id]
        online = snapshot['connected'] and not self.robot_mode.currentIndex()
        card['status'].setText('●  VIRTUAL — OK' if online else '●  OFFLINE')
        card['status'].setObjectName('chipGreen' if online else 'chipNeutral')
        card['status'].style().unpolish(card['status'])
        card['status'].style().polish(card['status'])
        card['toggle'].setText('Disconnect virtual' if online else 'Connect virtual')
        card['toggle'].setEnabled(True)
        reg = snapshot['registers']
        f = card['fields']
        f['Connection'].setText('Virtual connected' if online else 'Not connected')
        f['Controller model'].setText('Unknown — awaiting Yaskawa')
        f['Servo status'].setText('Not controlled')
        f['Active checkpoint'].setText(str(reg['I011']) if reg['I011'] else '—')
        f['Heartbeat'].setText(str(reg['I010']) if online else '—')
        timing = '—' if not online or snapshot['poll_mean_ms'] is None else (
            f"{snapshot['poll_mean_ms']} / {snapshot['poll_p95_ms']} / {snapshot['poll_max_ms']} ms")
        f['Local poll mean / P95 / max'].setText(timing)
        if hasattr(self, 'register_table') and not self.robot_mode.currentIndex():
            for key, val in reg.items():
                if key in self.reg_rows:
                    item = self.register_table.item(self.reg_rows[key], robot_id+2)
                    item.setText(str(val) if online else '—')

    def telemetry_note(self, robot_id, message):
        stamp = datetime.now().strftime('%H:%M:%S')
        text = f'[{stamp}] [Robot {robot_id}] {message}' if robot_id else f'[{stamp}] [System] {message}'
        self.telemetry_logs.append([datetime.now().isoformat(), robot_id, message])
        if hasattr(self, 'telemetry_console'):
            self.telemetry_console.append(text)

    def export_telemetry(self):
        filename, _ = QFileDialog.getSaveFileName(self, 'Export virtual communication diagnostics',
                                                   'robot_simulation_diagnostics.csv', 'CSV Files (*.csv)')
        if not filename:
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as handle:
                writer = csv.writer(handle)
                writer.writerow(['timestamp', 'robot_id', 'event', 'data_type'])
                for entry in self.telemetry_logs:
                    writer.writerow([*entry, 'SIMULATION / LOCAL TIMING'])
                for robot_id, robot in self.telemetry.items():
                    snap = robot.snapshot()
                    writer.writerow([datetime.now().isoformat(), robot_id,
                        f"Local poll samples={snap['samples']}, mean={snap['poll_mean_ms']} ms, "
                        f"P95={snap['poll_p95_ms']} ms, max={snap['poll_max_ms']} ms", 'SIMULATION'])
        except OSError as exc:
            QMessageBox.warning(self, 'Export failed', str(exc))
            return
        self.telemetry_note(0, f'Diagnostics exported to {filename}')

    def build_cameras(self):
        page, v = self.page('4K Camera Configuration',
                            'Camera profiles used for each inspection view and virtual capture in Phase 1')
        grid = QGridLayout()
        grid.setSpacing(16)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        v.addLayout(grid)
        for col, view_string in enumerate(['Sidewall 1, Inner Side', 'Tread, Bead, Sidewall 2']):
            camera = col + 1
            w, q = surface(kind='stationCard', padding=(20, 20, 20, 22), spacing=14)
            grid.addWidget(w, 0, col)
            head = QHBoxLayout()
            head.addWidget(icon_tile('camera', 'iconBlue' if col else 'iconPurple', 56, 29))
            titles = QVBoxLayout()
            titles.addWidget(label(f'Camera {camera}', size=22, color=INK, bold=True))
            titles.addWidget(label('VIRTUAL 4K LINE SCAN', size=12, color=PURPLE, bold=True))
            head.addLayout(titles)
            head.addStretch()
            q.addLayout(head)
            for key, val in [
                ('Assigned views', view_string), ('Resolution width', '4096 pixels'),
                ('Virtual frame height', '1024 lines'), ('Line trigger', 'Simulated encoder'),
                ('Exposure', 'To configure per view'), ('Camera serial', 'Not connected')
            ]:
                field_pair(q, key, val)
        info, iv = surface(kind='stationCard', padding=(20, 19, 20, 19), spacing=10)
        v.addWidget(info)
        r = QHBoxLayout()
        r.addWidget(icon_tile('layers', 'iconPurple'))
        r.addWidget(label('Camera Integration Boundary', 'section'))
        r.addStretch()
        iv.addLayout(r)
        iv.addWidget(label('The production acquisition adapter will use the selected camera SDK and spindle encoder. '
                           'UDP/HSES polling must not be used as the LineStart timing source.', color='#4E587F'))
        v.addStretch()
        return page

    def build_mapping(self):
        page, v = self.page('Station & Checkpoint Mapping',
                            'Logical job-to-view assignments for the five-image workflow')
        w, q = surface(kind='stationCard', padding=(18, 20, 18, 20), spacing=15)
        v.addWidget(w)
        r = QHBoxLayout()
        r.addWidget(icon_tile('layers', 'iconPurple', 48, 26))
        r.addWidget(label('Inspection View Assignments', 'section'))
        r.addStretch()
        q.addLayout(r)
        records = [
            ('S1', 'Robot 1', 'Camera 1', '101', 'Sidewall 1'),
            ('S1', 'Robot 1', 'Camera 1', '102', 'Inner Side'),
            ('S2', 'Robot 2', 'Camera 2', '201', 'Tread'),
            ('S2', 'Robot 2', 'Camera 2', '202', 'Bead'),
            ('S2', 'Robot 2', 'Camera 2', '203', 'Sidewall 2')
        ]
        t = QTableWidget(len(records), 5)
        t.setHorizontalHeaderLabels(['Station', 'Robot', 'Camera', 'Proposed Checkpoint', 'Inspection View'])
        table_config(t, 59)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for i, record in enumerate(records):
            for j, cell in enumerate(record):
                t.setItem(i, j, table_item(cell))
        t.setFixedHeight(350)
        q.addWidget(t)
        note, nv = surface(kind='noteInfo', padding=(15, 15, 15, 15))
        nv.addWidget(label('ⓘ  Checkpoint IDs are provisional and exist only in the simulator. '
                           'Physical robot jobs and safety-approved station transfer logic are not implemented.',
                           color='#524383', size=11))
        q.addWidget(note)
        v.addStretch()
        return page

    def build_history(self):
        page, v = self.page('Capture History',
                            'Search-ready simulated capture records  •  barcode / SKU / operation traceability')
        actions = QHBoxLayout()
        actions.addStretch()
        self.history_search = QLineEdit()
        self.history_search.setPlaceholderText('Search barcode, cycle or SKU...')
        self.history_search.setMinimumWidth(270)
        self.history_search.textChanged.connect(self.filter_history)
        actions.addWidget(self.history_search)
        refresh = btn('Refresh', 'primary')
        set_button_icon(refresh,'refresh','white',16)
        refresh.clicked.connect(self.refresh_history)
        actions.addWidget(refresh)
        open_folder = btn('Open Capture Folder', 'secondary')
        set_button_icon(open_folder,'folder','purple',16)
        open_folder.clicked.connect(self.open_selected)
        actions.addWidget(open_folder)
        v.addLayout(actions)
        w, q = surface(kind='stationCard', padding=(16, 18, 16, 20), spacing=16)
        v.addWidget(w)
        hr = QHBoxLayout()
        hr.addWidget(icon_tile('layers', 'iconPurple'))
        hr.addWidget(label('Last 150 Cycles', 'section'))
        hr.addStretch()
        q.addLayout(hr)
        self.history = QTableWidget(0, 7)
        self.history.setHorizontalHeaderLabels(['Cycle ID', 'Barcode', 'SKU', 'Status', 'Images', 'Started', 'Folder'])
        table_config(self.history, 42)
        self.history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.history.horizontalHeader().setStretchLastSection(True)
        self.history.setMinimumHeight(385)
        self.history.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.history.cellDoubleClicked.connect(lambda row, _col: self.open_selected())
        q.addWidget(self.history)
        self.history_hint = label('Double-click a cycle to open its folder. Select a row before using Open Capture Folder.',
                                  size=11, color=MUTED)
        q.addWidget(self.history_hint)
        v.addStretch()
        return page

    def build_diagnostics(self):
        page, v = self.page('System Diagnostics',
                            'Readiness, communication tests, and commissioning safeguards')
        items = [
            ('robot', 'Robot Communications', 'Simulation only. HSES network connections are disabled.',
             '●  SIMULATION ONLY', 'chipPurple', 'iconPurple'),
            ('camera', 'Camera Acquisition', 'Virtual grayscale patterned PNGs; not actual camera frames.',
             '✓  VIRTUAL INPUT', 'chipGreen', 'iconBlue'),
            ('activity', 'Encoder', 'Simulated timing only. Production LineStart requires encoder synchronization.',
             'ⓘ  SIMULATED TIMING', 'chipBlue', 'iconPurple'),
            ('shield', 'Safety and Robot Jobs', 'No servo enable, reset, job start, motion, or live variable writes implemented.',
             '✓  NO LIVE WRITES', 'chipGreen', 'iconGreen'),
            ('database', 'Storage', 'SQLite event history and per-cycle JSON manifests.',
             '✓  OPERATIONAL', 'chipGreen', 'iconBlue'),
            ('server', 'Controller Integration', 'Pending Yaskawa controller model, HSES options and approved variable mapping.',
             '◷  PENDING', 'chipNeutral', 'iconPurple')
        ]
        for symbol, name, detail, status, style, icon_style in items:
            w, q = surface(kind='diagnosticCard', padding=(18, 16, 18, 16), spacing=0)
            v.addWidget(w)
            h = QHBoxLayout()
            h.setSpacing(14)
            h.addWidget(icon_tile(symbol, icon_style, 52, 26))
            column = QVBoxLayout()
            column.setSpacing(5)
            column.addWidget(label(name, 'section'))
            column.addWidget(label(detail, color='#5F6A8A', size=12))
            h.addLayout(column, 1)
            h.addSpacing(18)
            h.addWidget(chip(status, style))
            q.addLayout(h)
        v.addStretch()
        return page

    # --- Existing simulator lifecycle retained ---
    def start_cycle(self):
        try:
            self.reset_live_tiles()
            selection = self.sku.currentData()
            if not selection:
                raise ValueError('Choose a simulation-active SKU or legacy simulation SKU.')
            code, version = selection
            self.sim.start(self.barcode.text(), code, recipe_version=version)
        except Exception as ex:
            QMessageBox.warning(self, 'Unable to start simulation', str(ex))

    def reset_live_tiles(self):
        for t in self.tiles.values():
            t.reset()
        self.progress_bar.setValue(0)
        self.progress_text.setText('0 / 5 images (0%)')
        for status in self.station_status.values():
            status.setText('●  WAITING')
            status.setObjectName('chipNeutral')
            status.style().unpolish(status)
            status.style().polish(status)

    def on_started(self, cycle_id):
        for robot in self.telemetry.values(): robot.cycle_start()
        self.capture_state.setText('Running')
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        for badge in self.station_status.values():
            badge.setText('●  CAPTURING')
            badge.setObjectName('chipGreen')
            badge.style().unpolish(badge)
            badge.style().polish(badge)
        self.console.append('[SYSTEM] ' + cycle_id)

    def on_progress(self, station, view, state):
        robot_id = 1 if station == 'S1' else 2
        self.telemetry[robot_id].on_checkpoint(view, state)
        tile = self.tiles[view]
        if state == 'CAPTURING':
            tile.capturing()
            return
        if state == 'DONE':
            path = self.sim.folder / station / f'{view}.png'
            tile.complete(path)
            count = len(self.sim.info['images'])
            self.progress_bar.setValue(count)
            self.progress_text.setText(f'{count} / 5 images ({count * 20}%)')
            if view == VIEWS[station][-1][0]:
                badge = self.station_status[station]
                badge.setText('✓  COMPLETE')

    def log_event(self, station, message):
        ts = datetime.now().strftime('%H:%M:%S')
        self.console.append(f'[{ts}] [{station}] {message}')

    def on_finished(self, cycle_id, status):
        for robot in self.telemetry.values(): robot.cycle_finish(status == 'COMPLETE')
        self.capture_state.setText(status.title())
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        for st, badge in self.station_status.items():
            if self.sim.info['stations'][st] == 'DONE':
                badge.setText('✓  COMPLETE')
                badge.setObjectName('chipGreen')
            elif status != 'COMPLETE':
                badge.setText('■  ' + status)
                badge.setObjectName('chipRed')
            badge.style().unpolish(badge)
            badge.style().polish(badge)
        self.refresh_history()

    def refresh_history(self):
        if not hasattr(self, 'history'):
            return
        try:
            rows = get_cycles()
            self.history.setRowCount(len(rows))
            for i, record in enumerate(rows):
                for j, value in enumerate(record):
                    item = table_item(value)
                    if j == 3:
                        if str(value) == 'COMPLETE':
                            item.setForeground(QColor('#158655'))
                        elif str(value) in ('STOPPED', 'FAILED'):
                            item.setForeground(QColor('#BA4050'))
                    self.history.setItem(i, j, item)
            self.filter_history(self.history_search.text() if hasattr(self, 'history_search') else '')
        except Exception as ex:
            self.history_hint.setText(f'Unable to refresh: {ex}')

    def filter_history(self, value):
        if not hasattr(self, 'history'):
            return
        needle = str(value).strip().lower()
        for r in range(self.history.rowCount()):
            row = ' '.join(self.history.item(r, c).text() for c in range(self.history.columnCount())
                           if self.history.item(r, c))
            self.history.setRowHidden(r, needle not in row.lower())

    def open_selected(self):
        row = self.history.currentRow()
        if row < 0:
            QMessageBox.information(self, 'Select a capture', 'Select a capture-history row first.')
            return
        item = self.history.item(row, 6)
        if not item:
            return
        p = Path(item.text())
        if not p.exists():
            QMessageBox.warning(self, 'Folder not found', str(p))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))

    def closeEvent(self, event):
        for device in self.hardware_robots.values(): device.disconnect_readonly()
        if self.sim.running:
            answer = QMessageBox.question(self, 'Stop running simulation?',
                                           'Closing will mark the running simulated cycle STOPPED.')
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.sim.stop()
        for controller in self.telemetry.values():
            controller.timer.stop()
        super().closeEvent(event)
