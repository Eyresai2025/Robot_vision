"""Offline-safe per-view software capture integration boundary.

Simulation backend is deliberately distinct from real LUCID acquisition. Manual
and robot-ready gates BOTH call the same software-start entrypoint, and the
camera lease prevents overlapping captures on a shared camera.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime,timezone
from pathlib import Path
from . import camera_profiles as cp
from .store import DATA

OUT=DATA/'camera_software_tests'

class SharedCameraLease:
    def __init__(self):
        self._locks={name:threading.Lock() for name in ('camera_1','camera_2')}
        self._active={}
    def capture(self,sku,version,view,profile,barcode,mode='MANUAL_SOFTWARE',backend='SIMULATION'):
        if view not in cp.VIEWS:raise ValueError('Invalid inspection view')
        camera_id=cp.CAMERAS[view]
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',barcode):raise ValueError('Invalid barcode')
        errors=cp.profile_checks(profile)
        if errors:raise ValueError('Profile incomplete: '+'; '.join(errors))
        lock=self._locks[camera_id]
        if not lock.acquire(blocking=False):raise RuntimeError(f'{camera_id} busy: profile cannot switch during active capture')
        try:
            if backend!='SIMULATION':
                raise RuntimeError('Real camera acquisition intentionally disabled in this offline-tested build. '
                                   'The LUCID Arena adapter must pass bench qualification before enabling hardware.')
            from .virtual_camera import generate
            tag=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+uuid.uuid4().hex[:6]
            target=OUT/barcode/f'{sku}_v{version}'/tag
            target.mkdir(parents=True,exist_ok=False)
            image=generate(view,tag)
            file=target/f'{view}.png'
            if not image.save(str(file),'PNG'):raise IOError('Failed to save synthetic preview')
            p=cp.normalize_profile(profile)
            info={'mode':'SIMULATION_ONLY', 'trigger_request':mode,'camera':camera_id,
                  'sku':sku,'version':version,'barcode':barcode,'view':view,
                  'profile':p,'image':str(file),'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
                  'captured_at':datetime.now(timezone.utc).isoformat(),
                  'note':'Synthetic 4096x1024 example only. NOT a real camera capture.'}
            meta=target/'capture.json';meta.write_text(json.dumps(info,indent=2),encoding='utf-8')
            return info
        finally:
            lock.release()

CAPTURE_LEASE=SharedCameraLease()
