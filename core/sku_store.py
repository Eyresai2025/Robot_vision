"""Local versioned SKU recipe storage. No hardware output is performed here.

Recipe versions are immutable: every revision inserts a new row. SQLite is the
source of truth; exported JSON is a readable, replaceable snapshot.
"""
import json
import re
import sqlite3
import os
from pathlib import Path
from .store import DATA, timestamp
from . import camera_profiles as camcfg

DB = DATA / 'ceat_cycles.sqlite3'
RECIPES = DATA / 'recipes'
SKU_RE = re.compile(r'^[A-Za-z0-9_.-]{1,64}$')
VIEWS = ('sidewall1', 'inner', 'tread', 'bead', 'sidewall2')
VIEW_NAMES = {'sidewall1':'Sidewall 1','inner':'Inner Side','tread':'Tread','bead':'Bead','sidewall2':'Sidewall 2'}
ASSIGNMENTS = {
    'sidewall1': ('S1', 'Robot 1', 'Camera 1'),
    'inner': ('S1', 'Robot 1', 'Camera 1'),
    'tread': ('S2', 'Robot 2', 'Camera 2'),
    'bead': ('S2', 'Robot 2', 'Camera 2'),
    'sidewall2': ('S2', 'Robot 2', 'Camera 2'),
}
DEFAULT_CP = {'sidewall1':'101', 'inner':'102', 'tread':'201', 'bead':'202', 'sidewall2':'203'}


def initialize():
    DATA.mkdir(parents=True, exist_ok=True)
    RECIPES.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as db:
        db.execute('PRAGMA foreign_keys = ON')
        db.execute('''CREATE TABLE IF NOT EXISTS skus (
            code TEXT PRIMARY KEY, tyre_width INTEGER NOT NULL, aspect_ratio INTEGER NOT NULL,
            rim_inches REAL NOT NULL, nominal_rpm REAL NOT NULL,
            description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL)''')
        db.execute('''CREATE TABLE IF NOT EXISTS sku_recipe_versions (
            code TEXT NOT NULL, version INTEGER NOT NULL, status TEXT NOT NULL,
            data_json TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY (code,version), FOREIGN KEY (code) REFERENCES skus(code))''')
        # Legacy V5 selections remain operable in SIMULATION mode only.
        db.execute('''CREATE TABLE IF NOT EXISTS legacy_simulation_skus (
            code TEXT PRIMARY KEY)''')
        for code in ('SKU_001','SKU_002','SKU_003'):
            db.execute('INSERT OR IGNORE INTO legacy_simulation_skus(code) VALUES (?)', (code,))


def initial_recipe():
    return {
        'code':'CEAT_195_65_R15', 'width':'195', 'aspect':'65', 'rim':'15',
        'rpm':'60', 'description':'', 'station_confirmed':True,
        'checkpoints': dict(DEFAULT_CP),
        'camera_profiles': {key:camcfg.default_profile() for key in VIEWS},
        'calibration_reviewed':False,
        'notes':'',
    }


def normalize(data):
    d = initial_recipe()
    d.update({key:val for key,val in data.items() if key in d})
    d['code'] = str(d['code']).strip().upper()
    if not SKU_RE.fullmatch(d['code']):
        raise ValueError('SKU code must be 1–64 letters, numbers, underscores, dots or hyphens.')
    try:
        width, aspect = int(str(d['width'])), int(str(d['aspect']))
        rim, rpm = float(str(d['rim'])), float(str(d['rpm']))
    except ValueError as ex:
        raise ValueError('Width, aspect ratio, rim diameter and RPM must be numeric.') from ex
    if not (80 <= width <= 500 and 20 <= aspect <= 100 and 8 <= rim <= 30 and 0 < rpm <= 250):
        raise ValueError('Check tyre values: width 80–500 mm, aspect 20–100%, rim 8–30 inches, RPM >0–250.')
    d['width'],d['aspect'],d['rim'],d['rpm'] = width,aspect,rim,rpm
    if len(str(d.get('description',''))) > 1000: raise ValueError('Description exceeds 1000 characters.')
    cps = d.get('checkpoints') or {}
    d['checkpoints'] = {key:str(cps.get(key,'')).strip()[:40] for key in VIEWS}
    profiles = d.get('camera_profiles') or {}
    d['camera_profiles'] = {}
    for key in VIEWS:
        src = profiles.get(key) or {}
        d['camera_profiles'][key] = camcfg.normalize_profile(src)
    d['station_confirmed'] = bool(d.get('station_confirmed'))
    d['calibration_reviewed'] = bool(d.get('calibration_reviewed'))
    return d


def validation(data):
    d = normalize(data)
    checks = [('Tyre specifications', True, 'Tyre specification and nominal RPM entered'),
              ('Station assignment',d['station_confirmed'], 'Two views at S1; three views at S2')]
    cp_values = list(d['checkpoints'].values())
    checks.append(('Checkpoint references',all(cp_values) and len(set(cp_values))==5,
                   'Five distinct proposed checkpoint references required'))
    problems = {k:camcfg.profile_checks(d['camera_profiles'][k]) for k in VIEWS}
    profiles_good = all(not errors for errors in problems.values())
    problem_summary = '; '.join(f'{VIEW_NAMES[k]}: {", ".join(errors[:2])}'
                                for k,errors in problems.items() if errors)
    checks.append(('Software-start camera profiles', profiles_good,
                   problem_summary or 'Five views configured; no encoder/hardware trigger'))
    checks.append(('Simulated calibration reviewed',d['calibration_reviewed'],
                   'Simulation-only visual review; not physical calibration'))
    checks.append(('Physical hardware calibration',False,'Not available in simulator'))
    checks.append(('Production engineer approval',False,'Pending controlled commissioning'))
    return checks


def save_recipe(data, status='DRAFT'):
    d=normalize(data)
    allowed={'DRAFT','REVIEWED','SIM_ACTIVE'}
    if status not in allowed: raise ValueError('Unknown recipe status')
    if status=='SIM_ACTIVE' and not all(ok for _,ok,_ in validation(d)[:5]):
        raise ValueError('Complete simulated recipe checks before simulation activation.')
    now=timestamp()
    with sqlite3.connect(DB) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT version FROM sku_recipe_versions WHERE code=? ORDER BY version DESC LIMIT 1', (d['code'],)).fetchone()
        version=(row[0]+1) if row else 1
        old=db.execute('SELECT code FROM skus WHERE code=?', (d['code'],)).fetchone()
        if old:
            db.execute('UPDATE skus SET tyre_width=?,aspect_ratio=?,rim_inches=?,nominal_rpm=?,description=?,updated_at=? WHERE code=?',
                       (d['width'],d['aspect'],d['rim'],d['rpm'],d['description'],now,d['code']))
        else:
            db.execute('INSERT INTO skus VALUES (?,?,?,?,?,?,?,?)',
                       (d['code'],d['width'],d['aspect'],d['rim'],d['rpm'],d['description'],now,now))
        db.execute('INSERT INTO sku_recipe_versions VALUES (?,?,?,?,?)',
                   (d['code'],version,status,json.dumps(d,sort_keys=True),now))
    result={'sku':d['code'],'version':version,'status':status,'created_at':now,'recipe':d,
            'simulation_only':True,'physical_robot_authorized':False}
    folder=RECIPES/d['code'];folder.mkdir(parents=True,exist_ok=True)
    out=folder/f'recipe_v{version}.json';tmp=out.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(result,indent=2), encoding='utf-8')
    os.replace(tmp,out)
    camcfg.export_snapshot(result,RECIPES)
    return result


def list_skus():
    with sqlite3.connect(DB) as db:
        return db.execute('''SELECT s.code,s.tyre_width,s.aspect_ratio,s.rim_inches,
            r.version,r.status,s.updated_at FROM skus s JOIN sku_recipe_versions r
            ON r.code=s.code AND r.version=(SELECT MAX(version) FROM sku_recipe_versions WHERE code=s.code)
            ORDER BY s.updated_at DESC,s.code''').fetchall()


def get_recipe(code,version=None):
    with sqlite3.connect(DB) as db:
        if version is None:
            row=db.execute('SELECT version,status,data_json FROM sku_recipe_versions WHERE code=? ORDER BY version DESC LIMIT 1',(code,)).fetchone()
        else:
            row=db.execute('SELECT version,status,data_json FROM sku_recipe_versions WHERE code=? AND version=?',(code,version)).fetchone()
    if row is None: return None
    return {'sku':code,'version':row[0],'status':row[1],'recipe':json.loads(row[2])}


def selectable_skus():
    """All simulation-ready recipes + legacy V5 simulation SKUs (no production authorization)."""
    with sqlite3.connect(DB) as db:
        active=db.execute('''SELECT code,MAX(version) FROM sku_recipe_versions
            WHERE status='SIM_ACTIVE' GROUP BY code ORDER BY code''').fetchall()
        legacy=[r[0] for r in db.execute('SELECT code FROM legacy_simulation_skus ORDER BY code')]
    return [(code,f'{code}  ·  V{version} (Simulation)',version) for code,version in active] + [
        (x,x+'  ·  Legacy simulation',0) for x in legacy]
