YMConnect 1.1.10 - read-only bridge patch for EyRes QC+ Robot Vision

1. BACK UP D:\CEAT_Robot_Vision\bridge\Program.cs
2. Replace it with Program_YMConnect_v1_1_10.cs from this zip, renamed Program.cs.
3. Keep your current YMConnectReadOnlyBridge.csproj unchanged.
4. CMD commands:
   cd /d D:\CEAT_Robot_Vision\bridge
   dotnet build -c Release
   dotnet publish -c Release -r win-x64 --self-contained false

5. SAFE OFFLINE SDK PROBE (no controller IP, no network access):
   cd /d D:\CEAT_Robot_Vision
   bridge\bin\Release\net8.0\win-x64\publish\YMConnectReadOnlyBridge.exe --inspect --sdk "D:\YMConnect\YMConnectDotNet_1_1_10_Windows\YMConnect_CS.dll"

This probe lists the actual VariablesInterface properties and confirms DLL loading.
Leave config/hardware_readonly.json enabled:false until controller model/IP, approved
reads, engineering authorization and read-only status tests are confirmed.

First approved test of a real controller (ONLY after reviewing the probe output):
  bridge\bin\Release\net8.0\win-x64\publish\YMConnectReadOnlyBridge.exe --ip ACTUAL_APPROVED_IP --sdk "D:\YMConnect\YMConnectDotNet_1_1_10_Windows\YMConnect_CS.dll" --interval 1000

No --reads initially. Stop the loop using Ctrl+C. No motion, variable writes, servo controls, or JOB changes are implemented.

IMPORTANT: This bridge uses reflection and has not been compiled or executed against Yaskawa's
SDK in this environment. A StatusInfo code not exposed as StatusCode or Code is explicitly
marked unverified, rather than guessed as success. Do not infer controller readiness from a
mere TCP/SDK connection.
