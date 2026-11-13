"""Image-derived column-gain software FFC for CEAT V9.

The algorithm is retained: column mean -> target statistic -> target / column mean,
clip gains -> multiply image in row blocks in-place, clamping to sensor dtype.
No external calibration reference is loaded; camera-side FFC is NOT enabled here.
Requires numpy only when this module is called (not for the offline GUI).
"""
from dataclasses import dataclass
import hashlib
import time
from typing import Any
import numpy as np

@dataclass(frozen=True)
class SoftwareFFCConfig:
    enabled: bool = True
    target_mode: str = 'PERCENTILE_95'
    gain_min: float = 1.0
    gain_max: float = 15.99
    row_block: int = 512
    fail_policy: str = 'raise'


def from_camera_profile(profile: dict) -> SoftwareFFCConfig:
    mode=str(profile.get('ffc_mode','SOFTWARE')).upper()
    if mode not in ('SOFTWARE','OFF'):
        raise ValueError('Camera-side FFC uses a different calibration workflow')
    cfg=SoftwareFFCConfig(
        enabled=mode=='SOFTWARE',
        target_mode=str(profile.get('ffc_target_mode','PERCENTILE_95')).upper(),
        gain_min=float(profile.get('ffc_gain_min','1.0')),
        gain_max=float(profile.get('ffc_gain_max','15.99')),
        row_block=int(profile.get('ffc_row_block','512')),
        fail_policy=str(profile.get('ffc_fail_policy','raise')).lower())
    if cfg.target_mode not in ('PERCENTILE_95','MAX','MEAN'):
        raise ValueError('Unsupported FFC target mode')
    if cfg.gain_min<=0 or cfg.gain_max<cfg.gain_min or cfg.row_block<1:
        raise ValueError('Invalid FFC gain limits or row block')
    if cfg.fail_policy not in ('raise','raw'):
        raise ValueError('Invalid FFC fail policy')
    return cfg


def compute_ffc_gain_from_image(image: np.ndarray, config: SoftwareFFCConfig):
    if image is None or image.ndim != 2 or image.shape[1]<=0 or not np.issubdtype(image.dtype,np.integer):
        raise ValueError('FFC requires a 2D integer mono image')
    columns=np.mean(image,axis=0,dtype=np.float64)
    if config.target_mode=='MAX': target=float(np.max(columns))
    elif config.target_mode=='MEAN': target=float(np.mean(columns))
    else: target=float(np.percentile(columns,95))
    gain=np.ones_like(columns,dtype=np.float64)
    valid=columns>1e-6
    gain[valid]=target/columns[valid]
    gain=np.clip(gain,config.gain_min,config.gain_max).astype(np.float32)
    return gain,{'target_mode':config.target_mode,'target':target,
        'profile_min':float(np.min(columns)),'profile_max':float(np.max(columns)),
        'profile_mean':float(np.mean(columns)),'gain_min':float(gain.min()),
        'gain_max':float(gain.max()),'gain_mean':float(gain.mean()),
        'gain_count':int(gain.size), 'gain_count_at_max':int(np.sum(gain>=config.gain_max)),
        'gain_sha256':hashlib.sha256(gain.tobytes()).hexdigest()}


def apply_software_ffc_inplace(image:np.ndarray,gain_values:np.ndarray,row_block:int)->int:
    if image.ndim!=2 or image.shape[1]!=gain_values.size or not np.issubdtype(image.dtype,np.integer):
        raise ValueError('FFC gain/image mismatch')
    height,width=image.shape
    if height==0:raise ValueError('Empty image')
    maximum=float(np.iinfo(image.dtype).max)
    gains=gain_values.reshape(1,-1).astype(np.float32,copy=False)
    block_rows=max(1,int(row_block))
    workspace=np.empty((min(block_rows,height),width),dtype=np.float32)
    saturated=0
    for first in range(0,height,block_rows):
        n=min(block_rows,height-first)
        chunk=workspace[:n]
        np.copyto(chunk,image[first:first+n],casting='unsafe')
        np.multiply(chunk,gains,out=chunk)
        saturated+=int(np.count_nonzero(chunk>=maximum))
        np.clip(chunk,0.0,maximum,out=chunk)
        np.copyto(image[first:first+n],chunk,casting='unsafe')
    return saturated


def correct_image_with_software_ffc(image:np.ndarray,config:SoftwareFFCConfig):
    if not config.enabled:return image,{'enabled':False}
    start=time.perf_counter()
    try:
        gains,stats=compute_ffc_gain_from_image(image,config)
        clipped=apply_software_ffc_inplace(image,gains,config.row_block)
    except Exception:
        # Honor the configured failure policy; never claim correction succeeded.
        if config.fail_policy=='raw':return image,{'enabled':False,'ffc_error':True,'policy':'raw'}
        raise
    stats.update(enabled=True,saturated_pixels=int(clipped),elapsed_sec=time.perf_counter()-start)
    return image,stats
