# EyRes QC+ Robot Vision — V7 YMConnect READ-ONLY Integration Starter

This is an upgrade of V6 (SKU Manager) for the team's two Yaskawa systems. The **robot arm models** visible on the supplied pendant photos are **GP8** and **GP12** (both display `YAS5.84.00A(EN)-00`). The controller models remain unconfirmed. **The screenshots do not include IP addresses**.

## What this code really does

- Preserves all V6 pages, simulated captures, SKU recipes and SQLite functionality.
- Adds two independently launched Windows YMConnect .NET reader processes to Robot Monitor.
- Defaults to **Simulation**. Actual hardware connection only starts after (1) official Yaskawa SDK installed, (2) bridge compiled, (3) explicit config enablement, and (4) operator clicks **Connect (read-only)**.
- The C# bridge uses YMConnect's `MotomanController.OpenConnection(string, out StatusInfo)` via runtime reflection to avoid including or redistributing proprietary binaries. It tries to call only **read-only** `GetStatusInformation` and explicitly approved **B/I Read** methods if supported in the version provided.
- Displays real connection attempt results, last SDK call duration, error events and values only where an actual read succeeded. If an SDK method differs, an unavailable value remains `—`; no dummy results are substituted.
- Does not provide `Write`, servo, hold, alarm reset, job start, job upload/download, motion, or camera trigger commands. Encoder-driven camera capture remains a separate future project stage.

**Limitations:** This workspace does not include Yaskawa SDK binaries and does not have a connected robot or Windows/.NET runtime. C# binary compilation and actual physical connection cannot be verified here. YMConnect assembly and method signatures may vary by downloaded release; integrator must reconcile the bridge's read method reflection with the exact SDK assembly supplied and test in an authorized environment. A successful OpenConnection alone does not prove that any particular variable/read operation is supported.

## 1. Required site information

Ask the integrator to confirm:

1. GP8 and GP12 **controller model and firmware** (separate from robot arm model).
2. Authorized management IP addresses and PC subnet for both systems (do not enter public IP addresses).
3. High Speed Ethernet Server available and correctly configured by Yaskawa/controls engineering. YMConnect typically uses UDP 10040/10041; validate with plant IT.
4. Documented read-only register map and data types. The existing B010 etc. values are **proposed**, not confirmed.
5. Site permission for PC monitoring while the cell is in a safe/test state; do not change controller parameters without the integrator.
6. Official SDK release and assembly layout. Use **v1.1.8 or newer** because the C# multi-controller bug was addressed in v1.1.8 (v1.1.10 listed in releases when checked).

## 2. Install the official YMConnect SDK (Windows)

Download the correct **.NET / Windows x64 release assets** from:

https://github.com/Yaskawa-Global/YMConnect/releases

The repository's source ZIP only contains the README/LICENSE; SDK binaries are separate release assets. Do **not** place SDK DLLs in the chat or public source repository. Keep the original vendor license and any accompanying native DLL files together per Yaskawa release instructions.

Install .NET SDK 8 (or a matching newer compatible SDK) on the Windows integration PC. From CMD:

```cmd
cd /d D:\EyRes_Robot_Vision_V7_Real_ReadOnly\bridge
dotnet publish -c Release -r win-x64 --self-contained false /p:PublishSingleFile=true
```

This step compiles the bridge source, which uses reflection and therefore needs no compile-time SDK reference. It **does not** prove runtime YMConnect compatibility.

Expected program file (depending on .NET build settings):

```
bridge\bin\Release\net8.0\win-x64\publish\YMConnectReadOnlyBridge.exe
```

## 3. Configure V7 read-only monitoring

Edit `config/hardware_readonly.json` (sample defaults deliberately disable network access):

```json
{
  "enabled": true,
  "sdk_dll": "D:/Vendor/YMConnect/YMConnect.dll",
  "bridge_executable": "D:/EyRes_Robot_Vision_V7_Real_ReadOnly/bridge/bin/Release/net8.0/win-x64/publish/YMConnectReadOnlyBridge.exe",
  "poll_interval_ms": 1000,
  "approved_read_variables": []
}
```

**Use the actual SDK managed assembly filename/path supplied in the official release.** The example `YMConnect.dll` must be changed if the vendor package uses a different location/name. Start with `approved_read_variables: []` and verify controller connectivity and status. Add only approved read entries later, for example `B010`, `I011`, when the robot integrator confirms these are allocated. Do not use the entire proposed handshake map blindly.

Do not reduce polling below 250 ms without load-testing with Yaskawa. Initial hardware polling is 1000 ms. Avoid competing network clients until confirmed supported.

## 4. Launch on your tested Windows Python environment

```cmd
cd /d D:\EyRes_Robot_Vision_V7_Real_ReadOnly
D:\CEAT_Robot_Vision\env_clean\Scripts\python.exe main.py
```

Go to **Robot Monitor** → switch **Communication mode** to **Hardware read-only (YMConnect bridge)**. Enter the approved IP for Robot 1 or 2, select **Save IP settings**, then click **Connect (read-only)** for just one robot initially. After successful single-robot tests, connect the other and compare timings.

### What data you should expect

- `Connected (read-only)` only if YMConnect `OpenConnection` succeeds.
- Last SDK read duration measures the **bridge's local SDK invocation** and is not a real-time trigger guarantee.
- `Controller model`: not verified from the supplied photos.
- `Servo status`: will show as unavailable or raw SDK information until the exact SDK status struct is mapped and validated.
- Variable cells remain blank unless approved and readable through the exact managed SDK version.

Save communication logs before stopping the program. If a controller is unreachable, the UI should report bridge errors rather than claiming an online connection.

## 5. Why the existing Python app remains the main application

```
EyRes QC+ PySide6 GUI
  ├─ Robot 1 QProcess → YMConnectReadOnlyBridge.exe → Controller attached to GP8
  ├─ Robot 2 QProcess → YMConnectReadOnlyBridge.exe → Controller attached to GP12
  └─ Existing V6 modules → SKU management / virtual capture / SQLite
```

The two C# processes have separate controller sessions. They communicate with the GUI by newline-delimited JSON over stdout. The PC bridge process is terminated when Disconnect is clicked. Its code contains **no hardware control methods**.

## 6. Next staged additions, after real read testing

- Integrator verifies the exact YMConnect status/variable read signatures and expands the read-only adapter to expose servo, job-running, alarm, position, controller/firmware information in structured fields.
- Test disconnect, controller off, one robot offline, two-robot coexistence, and sustained polling. Record real error/latency distribution.
- Confirm controller-side JOB handshake ownership and machine-safety architecture **before developing any writes**.
- Later connect the real 4K line-scan cameras and their **physical spindle encoders**; Ethernet polling does not generate LineStart pulses.

## Deliverables and checks

- `bridge/Program.cs`: live read-only YMConnect reader, no write APIs.
- `bridge/YMConnectReadOnlyBridge.csproj`: build metadata.
- `core/ymconnect_process.py`: one QProcess per robot, connection and error signals.
- `config/hardware_readonly.json`: fail-closed hardware enable/whitelist.
- `ui/main_window.py`: updated Robot Monitor mode and read-only controls.
- Syntax verified with `python -m compileall`. No actual Windows YMConnect build or real controller test has been performed.
