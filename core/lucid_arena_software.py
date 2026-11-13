"""EXPERIMENTAL LUCID Arena SOFTWARE-START adapter.

Not invoked by V9 GUI; requires supervised hardware bench verification for each
4K LUCID camera model/firmware and its actual line-timing configuration.
No robot writes, no hardware trigger, no external encoder. One camera / worker.

Arena API patterns: arena_api.system.system, device.nodemap,
start_stream/get_buffer/requeue_buffer/stop_stream, TriggerSoftware.execute().
"""
from __future__ import annotations
import ctypes
import time
from pathlib import Path

class LucidArenaSoftwareCamera:
    def __init__(self,serial):
        if not str(serial).strip():raise ValueError('Bind explicit camera serial; never take the first discovered device')
        self.serial=str(serial).strip();self.device=None;self._arena_system=None;self._streaming=False

    def connect(self):
        from arena_api.system import system
        matches=[]
        for info in system.device_infos:
            number=str(info.get('serial','') or info.get('serial_number',''))
            if number==self.serial:matches.append(info)
        if len(matches)!=1:raise RuntimeError(f'Expected exactly one LUCID camera with serial {self.serial}; found {len(matches)}')
        devices=system.create_device([matches[0]])
        if len(devices)!=1:raise RuntimeError('Camera could not be opened')
        self._arena_system=system;self.device=devices[0]

    def _node(self,name):
        if self.device is None:raise RuntimeError('Not connected')
        return self.device.nodemap.get_node(name)

    def _set(self,name,value,required=True):
        try:
            node=self._node(name)
            if node is None:raise RuntimeError('not exposed')
            node.value=value
            actual=node.value
            if str(actual)!=str(value) and not isinstance(value,(float,int)):
                raise RuntimeError(f'readback mismatch {actual} != {value}')
            if isinstance(value,(float,int)) and abs(float(actual)-float(value))>max(0.1,0.01*abs(float(value))):
                raise RuntimeError(f'readback mismatch {actual} != {value}')
            return actual
        except Exception:
            if required:raise RuntimeError(f'Cannot configure {name}={value}; verify node/model/firmware')
            return None

    def _execute(self,name):
        node=self._node(name)
        if node is None or not getattr(node,'is_writable',False):
            raise RuntimeError(f'{name} command unavailable/not writable')
        node.execute()

    def prepare(self,profile):
        """Always stop and re-arm between views. No setting change mid-capture."""
        from .camera_profiles import normalize_profile,profile_checks
        p=normalize_profile(profile);issues=profile_checks(p)
        if issues:raise ValueError('; '.join(issues))
        if p['ffc_mode']=='CAMERA_CALIBRATED':
            raise RuntimeError('Camera-side FFC requires separate camera calibration commissioning')
        if p['camera_serial'] and p['camera_serial']!=self.serial:
            raise RuntimeError('Recipe camera serial mismatch')
        if self._streaming:
            self.stop()
        try:self._execute('AcquisitionStop')
        except Exception:pass # some devices have not started acquisition
        self._set('TriggerMode','Off')
        self._set('Width',4096)
        self._set('PixelFormat','Mono8')
        # This is only valid if firmware offers internally timed line generation.
        # Explicitly disable LineStart external triggering; fail if unavailable.
        self._set('TriggerSelector','LineStart')
        self._set('TriggerMode','Off')
        self._set('AcquisitionLineRateEnable',True,required=False)
        self._set('AcquisitionLineRate',float(p['line_rate_hz']))
        self._set('ExposureAuto','Off',required=False)
        self._set('GainAuto','Off',required=False)
        self._set('ExposureTime',float(p['exposure_us']))
        self._set('Gain',float(p['gain_db']))
        # Each buffer contains lines smaller than total stitched image; camera Height
        # node must be checked against device limits on the actual unit.
        self._set('Height', min(int(p['frame_lines']),1024))
        self._set('TriggerSelector',p['start_selector'])
        self._set('TriggerSource','Software')
        self._set('TriggerMode','On')
        self.device.start_stream(8);self._streaming=True
        trigger=self._node('TriggerSoftware')
        if trigger is None or not getattr(trigger,'is_writable',False):
            self.stop();raise RuntimeError('Software trigger not armed after stream restart')
        return p

    def capture_bench(self,profile,output_tiff):
        """One triggered acquisition; persist 4K Mono8 stitched TIFF.

        Requires optional numpy + tifffile, LUCID Arena Python SDK, and a real
        camera confirmed to support Software AcquisitionStart + internal LineStart.
        THIS METHOD IS NOT CALLED FROM THE GUI IN THE OFFLINE VERSION.
        """
        import numpy as np
        import tifffile
        if self.device is None:raise RuntimeError('Connect before capture')
        p=self.prepare(profile)
        total=int(p['frame_lines']);width=4096
        if total>60000:raise ValueError('Bench cap: max 60000 lines until memory/throughput qualification')
        target=Path(output_tiff);target.parent.mkdir(parents=True,exist_ok=True)
        # Memory-mapped intermediate prevents allocating a multi-GB in-memory frame.
        scratch=target.with_suffix('.tmp.npy')
        array=np.lib.format.open_memmap(scratch,mode='w+',dtype='uint8',shape=(total,width))
        row=0;deadline=time.monotonic()+int(p['image_timeout_ms'])/1000.0
        try:
            self._execute('TriggerSoftware')
            while row<total:
                if time.monotonic()>=deadline:raise TimeoutError(f'Only {row}/{total} lines received')
                buf=self.device.get_buffer(timeout=500)
                try:
                    w,h=int(buf.width),int(buf.height)
                    size=int(getattr(buf,'size_filled',0) or getattr(buf,'size',0) or w*h)
                    if w!=width or h<=0 or size < w*h:raise RuntimeError('Incomplete/wrong-width Mono8 frame')
                    source=ctypes.addressof(buf.pbytes)
                    chunk=np.ctypeslib.as_array((ctypes.c_uint8*(w*h)).from_address(source)).reshape(h,w)
                    n=min(h,total-row)
                    array[row:row+n]=chunk[:n];row+=n
                finally:self.device.requeue_buffer(buf)
            # Same software-FFC computation on stitched 2D mono image.
            # This adapter is still bench-only and NOT invoked by the V9 GUI.
            ffc_stats={'enabled':False}
            if p['ffc_mode']=='SOFTWARE':
                from .software_ffc import from_camera_profile, correct_image_with_software_ffc
                _,ffc_stats=correct_image_with_software_ffc(array,from_camera_profile(p))
            array.flush()
            tifffile.imwrite(target,array,photometric='minisblack',compression=None)
            return {'path':str(target),'width':width,'height':row,'serial':self.serial,
                    'software_trigger':True,'ffc':ffc_stats}
        finally:
            del array
            try:scratch.unlink(missing_ok=True)
            finally:self.stop() # fresh full re-arm for the next inspection view

    def stop(self):
        if self.device is not None and self._streaming:
            try:self._execute('AcquisitionStop')
            except Exception:pass
            try:self.device.stop_stream()
            finally:self._streaming=False

    def close(self):
        self.stop()
        if self.device is not None and self._arena_system is not None:
            self._arena_system.destroy_device(self.device)
        self.device=None
