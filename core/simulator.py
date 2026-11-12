"""No robot network access, no servo commands, no control of physical machinery."""
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject, QTimer, Signal
from .store import CAPTURES, create_cycle, update_cycle, event, write_manifest, timestamp
from .virtual_camera import generate
import uuid, re, hashlib

VIEWS={'S1':['sidewall1','inner'],'S2':['tread','bead','sidewall2']}
CP={'sidewall1':101,'inner':102,'tread':201,'bead':202,'sidewall2':203}

class Simulation(QObject):
    progress=Signal(str,str,str) # station, view, state
    finished=Signal(str,str) # cycle id/status
    log=Signal(str,str) # station, message
    started=Signal(str)
    def __init__(self):
        super().__init__()
        self.running=False; self.tasks={}; self.timers=[];self.info=None;self.folder=None

    def emit(self,station,message):
        self.log.emit(station,message)
        if self.info: event(self.info['cycle_id'],station,message)

    def start(self,barcode,sku,recipe_version=0):
        if self.running: raise RuntimeError('Simulation already running')
        barcode=barcode.strip();sku=sku.strip()
        if not barcode or not sku: raise ValueError('Enter a barcode and SKU.')
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',barcode) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',sku):
            raise ValueError('Barcode and SKU can contain letters, numbers, underscore, dash and dot only.')
        cid='SIM-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:5].upper()
        folder=CAPTURES/barcode/cid;folder.mkdir(parents=True,exist_ok=False)
        self.folder=folder
        self.info={'cycle_id':cid,'barcode':barcode,'sku':sku,'simulation':True,'started_at':timestamp(),
                   'status':'RUNNING','recipe_version':recipe_version,
                   'recipe_mode':'SIMULATION_ONLY','images':{},'stations':{'S1':'RUNNING','S2':'RUNNING'}}
        create_cycle(cid,barcode,sku,folder,recipe_version)
        self.tasks={'S1':0,'S2':0};self.running=True
        self.started.emit(cid)
        self.emit('SYSTEM',f'Cycle {cid} started — SIMULATION ONLY')
        for station in ('S1','S2'):
            timer=QTimer(self);timer.setInterval(1250 if station=='S1' else 1530)
            timer.timeout.connect(lambda st=station:self._advance(st))
            timer.start();self.timers.append((station,timer))
        write_manifest(folder,self.info)
        return cid

    def _advance(self,station):
        if not self.running: return
        idx=self.tasks[station]
        if idx>=len(VIEWS[station]): return
        view=VIEWS[station][idx]
        self.emit(station,f'Robot checkpoint {CP[view]} acknowledged (virtual token {idx+1})')
        self.progress.emit(station,view,'CAPTURING')
        try:
            im=generate(view,self.info['cycle_id'])
            path=self.folder/station/f'{view}.png';path.parent.mkdir(exist_ok=True)
            if not im.save(str(path),'PNG'):raise RuntimeError('Image save failed')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            self.info['images'][view]={'station':station,'checkpoint':CP[view], 'file':str(path.relative_to(self.folder)),
                  'width':im.width(),'height':im.height(),'sha256':digest,'captured_at':timestamp(),'simulated':True}
            self.emit(station,f'{view} saved and verified ({im.width()}×{im.height()}, simulated)')
            self.progress.emit(station,view,'DONE')
            self.tasks[station]+=1
            if self.tasks[station]==len(VIEWS[station]):
                self.info['stations'][station]='DONE'
                for st,t in self.timers:
                    if st==station:t.stop()
                self.emit(station,'Station cycle completed')
            update_cycle(self.info['cycle_id'],'RUNNING',len(self.info['images']))
            write_manifest(self.folder,self.info)
            if all(self.tasks[st]==len(VIEWS[st]) for st in VIEWS):self._finish('COMPLETE')
        except Exception as ex:
            self.emit(station,f'FAULT: {ex}')
            self._finish('FAILED')

    def _finish(self,status):
        if not self.running:return
        self.running=False
        for st,timer in self.timers:timer.stop();timer.deleteLater()
        self.timers=[]
        self.info['status']=status;self.info['completed_at']=timestamp()
        update_cycle(self.info['cycle_id'],status,len(self.info['images']))
        write_manifest(self.folder,self.info)
        self.emit('SYSTEM',f'Cycle ended: {status} ({len(self.info["images"])}/5 views)')
        self.finished.emit(self.info['cycle_id'],status)

    def stop(self):
        if self.running:self._finish('STOPPED')
