"""V9 SKU-specific software-start camera profiles (no encoder or hardware trigger).

SQLite recipe versions remain canonical; this module exports immutable JSON snapshots
and validates switching/gating constraints. All operations are local file I/O.
"""
from __future__ import annotations
import copy
import json
import os
import re
from pathlib import Path

VIEWS = ('sidewall1', 'inner', 'tread', 'bead', 'sidewall2')
CAMERAS = {'sidewall1':'camera_1','inner':'camera_1',
           'tread':'camera_2','bead':'camera_2','sidewall2':'camera_2'}
TRIGGER_MODES = ('MANUAL_SOFTWARE','ROBOT_READY_SOFTWARE')
FFC_MODES = ('OFF','SOFTWARE','CAMERA_CALIBRATED')
START_SELECTOR = ('AcquisitionStart','FrameStart')
DEFAULT_LINE_SOURCE = 'INTERNAL_TIMED'   # Software-start is NOT software-per-line.


def default_profile():
    return {'exposure_us':'', 'gain_db':'0', 'frame_lines':'',
            'line_rate_hz':'', 'pixel_format':'Mono8', 'width':'4096',
            'capture_mode':'MANUAL_SOFTWARE', 'start_selector':'AcquisitionStart',
            'line_source':DEFAULT_LINE_SOURCE, 'trigger':'SOFTWARE_START',
            'ffc_mode':'SOFTWARE', 'ffc_target_mode':'PERCENTILE_95',
            'ffc_gain_min':'1.0', 'ffc_gain_max':'15.99', 'ffc_row_block':'512',
            'ffc_fail_policy':'raise',
            'image_timeout_ms':'15000', 'readiness_timeout_ms':'5000',
            'required_ready_value':'1', 'ready_variable':'',
            'checkpoint_variable':'',
            'camera_serial':'', 'illumination_profile':'',
            'profile_notes':''}


def normalize_profile(profile):
    p = default_profile()
    raw = profile if isinstance(profile,dict) else {}
    for key in p:
        if key in raw: p[key] = str(raw[key]).strip()[:500]
    # Convert legacy V8 encoder profile to MANUAL software-start (no encoder use).
    if raw.get('trigger') in ('SIMULATED_ENCODER','SPINDLE_ENCODER'):
        p['trigger'] = 'SOFTWARE_START'
    if p['capture_mode'] not in TRIGGER_MODES:
        p['capture_mode'] = 'MANUAL_SOFTWARE'
    # Migrate V9's reference-file choice to  calculated, per-image method.
    if p['ffc_mode']=='SOFTWARE_REFERENCE': p['ffc_mode']='SOFTWARE'
    if p['ffc_mode'] not in FFC_MODES: p['ffc_mode']='OFF'
    if p['ffc_target_mode'] not in ('PERCENTILE_95','MAX','MEAN'): p['ffc_target_mode']='PERCENTILE_95'
    if p['start_selector'] not in START_SELECTOR: p['start_selector'] = 'AcquisitionStart'
    p['line_source'] = DEFAULT_LINE_SOURCE
    p['pixel_format'] = 'Mono8' # First commissioning target only; expand after camera verification.
    p['width'] = '4096'
    p['trigger'] = 'SOFTWARE_START'
    return p


def profile_checks(p, *, offline=True):
    p=normalize_profile(p)
    errors=[]
    def num(name,lo,hi,integer=False):
        try:
            value=int(p[name]) if integer else float(p[name])
            if not lo <= value <= hi: raise ValueError()
        except (TypeError,ValueError): errors.append(f'{name}: expected {lo}–{hi}')
    num('exposure_us',1,1000000)
    num('gain_db',0,48)
    num('frame_lines',1,500000,True)
    num('line_rate_hz',1,100000)
    num('image_timeout_ms',1000,120000,True)
    num('readiness_timeout_ms',250,30000,True)
    try:
        if p['exposure_us'] and p['line_rate_hz'] and float(p['exposure_us'])*float(p['line_rate_hz']) >= 1000000:
            errors.append('Exposure must be below the line period (1,000,000 / line rate)')
    except ValueError: pass
    if p['capture_mode']=='ROBOT_READY_SOFTWARE':
        if not re.fullmatch(r'[BI]\d{1,4}',p['ready_variable'],re.I):
            errors.append('Ready-bit mode needs an approved B/I variable (e.g. B013)')
        if not re.fullmatch(r'[BI]\d{1,4}',p['checkpoint_variable'],re.I):
            errors.append('Robot ready mode requires an approved checkpoint variable (e.g. I011)')
        if p['required_ready_value'] not in ('0','1'):
            errors.append('Ready state value must be 0 or 1')
    if p['ffc_mode']=='SOFTWARE':
        if p['ffc_target_mode'] not in ('PERCENTILE_95','MAX','MEAN'):
            errors.append('FFC target mode must be PERCENTILE_95, MAX or MEAN')
        num('ffc_gain_min',0.001,1000)
        num('ffc_gain_max',0.001,1000)
        num('ffc_row_block',1,65536,True)
        try:
            if float(p['ffc_gain_max'])<float(p['ffc_gain_min']):
                errors.append('FFC gain maximum must be >= minimum')
        except ValueError: pass
        if p['ffc_fail_policy'] not in ('raise','raw'):
            errors.append('FFC failure policy must be raise or raw')
    if p['ffc_mode']=='CAMERA_CALIBRATED' and offline:
        # In simulation we can store it, but hardware still needs a calibration check.
        pass
    return errors


def export_snapshot(saved_result, recipe_root):
    """Atomic, versioned JSON export. Never silently overwrites a saved version."""
    sku,version=saved_result['sku'],saved_result['version']
    data=saved_result['recipe']
    folder=Path(recipe_root)/sku
    folder.mkdir(parents=True,exist_ok=True)
    doc={'schema_version':2, 'sku':sku,'recipe_version':version,
         'status':saved_result['status'], 'software_trigger_only':True,
         'hardware_authorized':False,
         'cameras':{'camera_1':{'views':['sidewall1','inner'],'serial':None},
                    'camera_2':{'views':['tread','bead','sidewall2'],'serial':None}},
         'profiles':{v:normalize_profile(data['camera_profiles'][v]) for v in VIEWS}}
    dest=folder/f'camera_profile_v{version}.json'
    temp=dest.with_suffix('.json.tmp')
    try:
        temp.write_text(json.dumps(doc,indent=2),encoding='utf-8')
        os.replace(temp,dest)
    finally:
        if temp.exists():temp.unlink()
    return dest


def load_snapshot(path,sku=None,version=None):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema_version')!=2 or data.get('software_trigger_only') is not True:
        raise ValueError('Wrong camera profile format / non-software trigger recipe')
    if sku is not None and data.get('sku')!=sku: raise ValueError('SKU mismatch')
    if version is not None and data.get('recipe_version')!=version: raise ValueError('Recipe version mismatch')
    if set(data.get('profiles',{}))!=set(VIEWS):raise ValueError('Expected exactly five view profiles')
    for view in VIEWS:
        data['profiles'][view]=normalize_profile(data['profiles'][view])
    return data


def apply_ready_gate(mode, *, robot_connected, sample_fresh, value, required='1', checkpoint_ok=True, rising_edge=True):
    """Pure guard used by offline tests; no writes or network access."""
    if mode=='MANUAL_SOFTWARE': return True, 'Operator manual software start'
    if mode!='ROBOT_READY_SOFTWARE':return False,'Unsupported capture mode'
    if not robot_connected:return False,'Robot monitoring is not connected'
    if not sample_fresh:return False,'Robot status sample is stale'
    if not checkpoint_ok:return False,'Robot checkpoint does not match selected view'
    if str(value)!=str(required):return False,'Ready bit not asserted'
    if not rising_edge:return False,'Waiting for a fresh ready-bit transition'
    return True,'Fresh approved robot ready bit and checkpoint confirmed'
