"""EyRes QC+ Robot Vision — Phase 1 (simulation only)."""
import sys
from pathlib import Path
from PySide6.QtGui import QIcon, QColor, QPalette
from PySide6.QtWidgets import QApplication
from core.store import initialize
from core.sku_store import initialize as initialize_skus
from ui.main_window import MainWindow


def main():
    initialize()
    initialize_skus()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    light = QPalette()
    light.setColor(QPalette.ColorRole.Window, QColor('#F7F8FF'))
    light.setColor(QPalette.ColorRole.WindowText, QColor('#17143C'))
    light.setColor(QPalette.ColorRole.Base, QColor('#FFFFFF'))
    light.setColor(QPalette.ColorRole.AlternateBase, QColor('#FAF9FF'))
    light.setColor(QPalette.ColorRole.Text, QColor('#17143C'))
    light.setColor(QPalette.ColorRole.Button, QColor('#FFFFFF'))
    light.setColor(QPalette.ColorRole.ButtonText, QColor('#17143C'))
    light.setColor(QPalette.ColorRole.Highlight, QColor('#7E4BE9'))
    light.setColor(QPalette.ColorRole.HighlightedText, QColor('#FFFFFF'))
    light.setColor(QPalette.ColorRole.ToolTipBase, QColor('#FFFFFF'))
    light.setColor(QPalette.ColorRole.ToolTipText, QColor('#17143C'))
    app.setPalette(light)
    app.setApplicationName("EyRes QC+ Robot Vision")
    app.setOrganizationName("EyRes.AI")
    logo = Path(__file__).resolve().parent / "assets" / "eyres_symbol.png"
    if logo.exists():
        app.setWindowIcon(QIcon(str(logo)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
