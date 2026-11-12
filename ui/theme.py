"""EyRes QC+ design tokens and Qt stylesheet; no hardware functionality."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QLinearGradient
from PySide6.QtWidgets import QWidget, QSizePolicy

INK = "#14113E"
MUTED = "#707A99"
PURPLE = "#6F38E9"
BLUE = "#109CE6"
MAGENTA = "#D935E9"
BORDER = "#E5E4F4"

QSS = r'''
QWidget { font-family: 'Segoe UI', 'Arial'; font-size: 12px; color:#17143C; }
QWidget#root, QWidget#body, QWidget#page, QStackedWidget#pageStack,
QScrollArea#pageScroll, QWidget#qt_scrollarea_viewport {
    background-color: #F7F8FF;
}
QFrame#sidebar { background-color: #FFFFFF; }
QWidget#page { color: #17143C; }

QFrame#sidebar { background-color:#FFFFFF; border-right:1px solid #E8E5F4; }
QFrame#topBar { background: #FFFFFF; border-bottom:1px solid #E9E6F4; }
QFrame#surface, QFrame#metricCard, QFrame#stationCard, QFrame#diagnosticCard {
    background: #FFFFFF; border:1px solid #E5E4F4; border-radius:16px; }
QFrame#metricCard { border-bottom:3px solid #BDB2FF; }
QFrame#metricPurple { background:white; border:1px solid #E7D9F9; border-bottom:3px solid #D94BE5; border-radius:16px; }
QFrame#metricBlue { background:white; border:1px solid #D8EEFC; border-bottom:3px solid #19BDEB; border-radius:16px; }
QFrame#metricGreen { background:white; border:1px solid #E1F2EA; border-bottom:3px solid #62D8A1; border-radius:16px; }
QFrame#stationCard { border:1px solid #DBD0FC; }
QFrame#captureTile { background: #FCFCFF; border:1px solid #E7E9F4; border-radius:12px; }
QFrame#noteInfo { background:#F5F2FF; border:1px solid #E8E0FD; border-radius:12px; }
QFrame#noteWarn { background:#FFF9F1; border:1px solid #F6DAB5; border-radius:12px; }
QFrame#iconPurple { background:#F0E7FF; border:none; border-radius:12px; }
QFrame#iconBlue { background:#E5F5FF; border:none; border-radius:12px; }
QFrame#iconGreen { background:#E6F9EE; border:none; border-radius:12px; }
QLabel#heading { font-size:27px; color:#15103F; font-weight:800; }
QLabel#subtitle { font-size:12px; color:#727B99; }
QLabel#section { font-size:16px; color:#181241; font-weight:800; }
QLabel#brand { font-size:20px; color:#17113C; font-weight:850; }
QLabel#brandSubtitle { color:#707A99; font-size:12px; }
QLabel#muted { color:#7380A1; }
QLabel#fieldLabel { color:#4F5475; font-size:11px; font-weight:650; }
QLabel#metricValue { font-size:19px; font-weight:800; color:#25134E; }
QLabel#chipGreen { color:#11744A; background:#E4F8EC; border-radius:12px; padding:5px 11px; font-size:11px; font-weight:750; }
QLabel#chipPurple { color:#6330CB; background:#F1E8FF; border-radius:12px; padding:5px 11px; font-size:11px; font-weight:750; }
QLabel#chipBlue { color:#1676BA; background:#E6F4FE; border-radius:12px; padding:5px 11px; font-size:11px; font-weight:750; }
QLabel#chipNeutral { color:#68728B; background:#F0F2F8; border-radius:12px; padding:5px 11px; font-size:11px; font-weight:750; }
QLabel#chipRed { color:#B43748; background:#FFECED; border-radius:12px; padding:5px 11px; font-size:11px; font-weight:750; }
QLabel#clientLogo { background-color:#FFFFFF; border:1px solid #E1E4F1; border-radius:11px; }
QLabel#ceatBadge { color:#1350A1; background:white; border:1px solid #E1E4F1; border-radius:11px; font-size:21px; font-weight:900; padding:4px 14px; }
QLabel#separator { background: #E6E4F3; }
QPushButton#nav { background:transparent; color:#1D2146; border:none; border-radius:10px; text-align:left; padding:12px 15px; font-weight:650; }
QPushButton#nav:hover { background:#F4EFFF; }
QPushButton#nav[active="true"] { background:#EDE0FF; color:#4C1FC6; font-weight:800; }
QPushButton#primary { border:none; border-radius:10px; background:#703AE7; color:white; padding:10px 17px; font-weight:750; }
QPushButton#primary:hover { background:#612DD2; }
QPushButton#secondary { border:1px solid #DCD8F2; border-radius:10px; background:white; color:#342B6A; padding:9px 15px; font-weight:700; }
QPushButton#secondary:hover { background:#F6F2FF; }
QPushButton#danger { border:1px solid #FACACD; border-radius:10px; background:#FFF1F2; color:#C23544; padding:9px 15px; font-weight:750; }
QPushButton#danger:hover { background:#FFE3E5; }
QPushButton#primary:disabled { background:#7854C9; color:#FFFFFF; border:none; }
QPushButton#secondary:disabled { background:#F6F5FB; color:#98A0B8; }
QPushButton#danger:disabled { background:#FFF4F4; color:#D9A1A7; border:1px solid #F2D6D8; }
QPushButton:disabled { opacity:0.85; }
QLineEdit, QComboBox { background:#FFFFFF; border:1px solid #DDE0EE; border-radius:9px; min-height:26px; padding:7px 11px; selection-background-color:#7E4BE9; }
QLineEdit:focus, QComboBox:focus { border:1px solid #8650ED; }
QComboBox { color:#1A1744; background-color:#FFFFFF; padding-right:28px; }
QComboBox:disabled { color:#9AA0B2; background-color:#F4F5FA; }
QComboBox::drop-down { background:#F9F7FF; border:0; border-left:1px solid #E4E2F4;
                      width:29px; border-top-right-radius:8px; border-bottom-right-radius:8px; }
QComboBox::down-arrow { image:none; border:0; width:0; height:0; }
QComboBox QAbstractItemView, QListView { background:#FFFFFF; color:#1A1744; border:1px solid #D8D4ED;
                  outline:0; selection-background-color:#EDE5FF; selection-color:#322071;
                  padding:5px; }
QComboBox QAbstractItemView::item { background:#FFFFFF; color:#1A1744; min-height:32px; padding:7px; }
QComboBox QAbstractItemView::item:selected { background:#EDE5FF; color:#322071; }
QProgressBar { border:none; border-radius:6px; background:#EDE7F8; height:12px; text-align:center; }
QProgressBar::chunk { border-radius:6px; background:#843FEE; }
QTextEdit#console { background-color:#1B2140; color:#FFFFFF; border:none; border-radius:10px; padding:11px; font-family:Consolas; font-size:11px; }
QTableWidget { border:1px solid #E4E2F4; border-radius:10px; background:white; gridline-color:#EAE8F5; alternate-background-color:#FAF9FF; selection-background-color:#EDE5FF; selection-color:#1B1647; }
QHeaderView::section { background:#EDEAFF; color:#20164D; border:0; border-right:1px solid #E0DDF3; padding:10px 9px; font-weight:800; }
QTableWidget::item { padding:7px; }
QScrollArea { background-color:#F7F8FF; border:0; }
QScrollBar:vertical { background:#F5F3FC; width:10px; }
QScrollBar::handle:vertical { background:#D3CAEE; border-radius:5px; min-height:40px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
'''


class WaveBanner(QWidget):
    """Soft vector brand ribbon, used as a decorative header accent."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(9)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        g = QLinearGradient(0, 0, r.width(), 0)
        g.setColorAt(0, QColor("#F4E9FF"))
        g.setColorAt(0.35, QColor("#E6B3F7"))
        g.setColorAt(0.65, QColor("#ECA0F7"))
        g.setColorAt(1, QColor("#9EEBFF"))
        painter.fillRect(r, g)
        painter.end()

class HeroPanel(QWidget):
    """Native Qt curved, translucent magenta-to-cyan accent for page headings."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(93)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        width, height = self.width(), self.height()
        start = width * .58
        p = QPainterPath()
        p.moveTo(start, 0)
        p.cubicTo(width * .72, -8, width * .77, 25, width, 0)
        p.lineTo(width, 62)
        p.cubicTo(width * .82, 24, width * .79, 22, start, 75)
        p.closeSubpath()
        g = QLinearGradient(start, 0, width, height)
        g.setColorAt(0, QColor(255, 220, 247, 0))
        g.setColorAt(.35, QColor(247, 164, 238, 100))
        g.setColorAt(.7, QColor(204, 191, 255, 115))
        g.setColorAt(1, QColor(155, 236, 252, 160))
        painter.fillPath(p, g)
        painter.end()

QSS += r"""
QFrame#stationCard, QFrame#diagnosticCard { background-color:#FFFFFF; }
QLabel#companyLogo { background:transparent; }
QTextEdit#console QWidget { color:#F5F5FF; background:transparent; }
"""

QSS += "\nQComboBox::down-arrow { image:url('" + str(__import__("pathlib").Path(__file__).resolve().parents[1] / "assets" / "icons" / "chevron_purple.png").replace("\\", "/") + "'); width:12px; height:12px; }\n"
