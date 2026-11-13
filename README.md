# EyRes QC+ Robot Vision — CEAT (V9, naming-corrected)

This source archive was checked for stale legacy naming and broken Python imports. It retains the two-robot simulator, read-only YMConnect bridge, SKU recipes, and five-view software-start camera profiles.

## Start on Windows

```cmd
cd /d D:\CEAT_Robot_Vision
py -3.11 -m venv env_clean
env_clean\Scripts\python.exe -m pip install -r requirements.txt
env_clean\Scripts\python.exe main.py
```

For an existing installation, **keep your own `data/`, `env_clean/`, and local vendor DLLs**. The patch only updates source files. The main software capture GUI is simulation-only; `core/lucid_arena_software.py` is experimental bench code, not wired to real capture yet.

## Corrected FFC module naming

- `core/software_ffc.py` provides column-based, per-image software FFC; no external reference image.
- `core/lucid_arena_software.py` imports it as `from .software_ffc import ...`.
- `tests/test_software_ffc.py` checks behavior.
- Delete the superseded legacy-named FFC source and test files from an existing install after backing up.
- `ffc_mode=SOFTWARE` selects the algorithm; `CAMERA_CALIBRATED` is a separate, uncommissioned feature.

## Capture layout

- GP8 / Camera 1: Sidewall 1 and Inner Side.
- GP12 / Camera 2: Tread, Bead, Sidewall 2.
- Manual software start or approved robot-ready-bit software start; no encoder or hardware LineStart trigger configured for this phase. The camera's internally timed line generation must be verified on physical hardware.
- SKU settings are stored as new versioned recipes; existing simulation-active versions are preserved.

## YMConnect read-only bridge

The verified v1.1.10 bridge uses `MotomanController.OpenConnection` (5 parameters) and `Status.ReadState(out ControllerStateData)`; configured approved B/I reads are read-only. Build with .NET 8 on Windows and place the vendor DLLs separately according to license terms. Keep `config/hardware_readonly.json` disabled until supervised commissioning.

```cmd
cd /d D:\CEAT_Robot_Vision\bridge
dotnet build -c Release
dotnet publish -c Release -r win-x64 --self-contained false
```

## Verification

```cmd
cd /d D:\CEAT_Robot_Vision
env_clean\Scripts\python.exe -m unittest discover -s tests -v
```

See `NAMING_AUDIT_AND_INSTALL.md` for the checks and upgrade instructions.
