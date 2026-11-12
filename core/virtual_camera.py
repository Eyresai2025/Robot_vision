"""Visual simulation only. Generated tyre-like patterns are NOT real camera captures."""
from PySide6.QtGui import QImage, QColor, QPainter, QPen, QFont
from PySide6.QtCore import Qt
import math, hashlib

WIDTH=4096
HEIGHT=1024 # deliberately short mock frame; editable for future camera profile

def generate(view, cycle_id):
    # Grayscale line-scan-like synthetic image, not an SDK camera output.
    im=QImage(WIDTH, HEIGHT, QImage.Format.Format_RGB32)
    im.fill(QColor('#171e2a'))
    p=QPainter(im)
    seed=int(hashlib.sha256((view+cycle_id).encode()).hexdigest()[:8],16)
    for y in range(0,HEIGHT,4):
        tone=50+int(27*math.sin(y/29+seed%19)+13*math.sin(y/8.3+seed%7))
        tone=max(18,min(115,tone))
        p.fillRect(0,y,WIDTH,4,QColor(tone,tone+3,tone+7))
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen=QPen(QColor(171,183,200,105)); pen.setWidth(6);p.setPen(pen)
    for x in range(-200,WIDTH+200,210):
        a=(x+(seed%53))%WIDTH
        for y in range(0,HEIGHT,95):
            if view=='tread': p.drawLine(a,y,a+95,y+76)
            elif view in ('sidewall1','sidewall2'): p.drawArc(a,y,280,235,5*16,155*16)
            elif view=='bead': p.drawLine(a,y,a+130,y+16)
            else: p.drawEllipse(a,y,75,28)
    p.setPen(QColor('#dbeafe'));p.setFont(QFont('Arial',36,QFont.Weight.Bold))
    p.drawText(40,70,f'SIMULATED • {view.upper()} • {cycle_id}')
    p.setPen(QColor('#ffbd7a'));p.setFont(QFont('Arial',20))
    p.drawText(40,106,'NOT A REAL TYRE IMAGE — VIRTUAL CAMERA')
    p.end()
    return im
