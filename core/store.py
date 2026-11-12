import json, sqlite3, datetime, os
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'data'
CAPTURES=DATA/'captures'
DB=DATA/'ceat_cycles.sqlite3'

def timestamp():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')

def initialize():
    CAPTURES.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS cycles (
          cycle_id TEXT PRIMARY KEY, barcode TEXT NOT NULL, sku TEXT NOT NULL,
          status TEXT NOT NULL, captured INTEGER NOT NULL, started TEXT NOT NULL,
          completed TEXT, folder TEXT NOT NULL)''')
        existing = {r[1] for r in db.execute('PRAGMA table_info(cycles)')}
        if 'recipe_version' not in existing:
            db.execute('ALTER TABLE cycles ADD COLUMN recipe_version INTEGER NOT NULL DEFAULT 0')
        db.execute('''CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT, cycle_id TEXT, ts TEXT NOT NULL,
          station TEXT, event TEXT NOT NULL)''')

def create_cycle(cycle_id,barcode,sku,folder,recipe_version=0):
    with sqlite3.connect(DB) as db:
        db.execute('''INSERT INTO cycles(cycle_id,barcode,sku,status,captured,started,completed,folder,recipe_version)
                      VALUES (?,?,?,?,?,?,?,?,?)''',
                   (cycle_id,barcode,sku,'RUNNING',0,timestamp(),None,str(folder),int(recipe_version)))

def update_cycle(cycle_id,status,captured):
    with sqlite3.connect(DB) as db:
        db.execute('UPDATE cycles SET status=?,captured=?,completed=? WHERE cycle_id=?',(status,captured,timestamp() if status!='RUNNING' else None,cycle_id))

def event(cycle_id,station,message):
    with sqlite3.connect(DB) as db:
        db.execute('INSERT INTO events(cycle_id,ts,station,event) VALUES (?,?,?,?)',(cycle_id,timestamp(),station,message))

def get_cycles():
    with sqlite3.connect(DB) as db:
        return db.execute('SELECT cycle_id,barcode,sku,status,captured,started,folder FROM cycles ORDER BY started DESC LIMIT 150').fetchall()

def get_events(cycle_id):
    with sqlite3.connect(DB) as db:
        return db.execute('SELECT ts,station,event FROM events WHERE cycle_id=? ORDER BY id',(cycle_id,)).fetchall()

def write_manifest(folder,info):
    path=Path(folder)/'manifest.json'
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(info,indent=2),encoding='utf-8')
    os.replace(tmp,path)
