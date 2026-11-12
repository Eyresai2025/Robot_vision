YMConnect SDK Inspector - no robot connection, no API calls, no writes

1. Extract this folder to D:\CEAT_Robot_Vision\sdk_inspector
2. Open Command Prompt and run:
   cd /d D:\CEAT_Robot_Vision\sdk_inspector
   dotnet run --project SDKInspector.csproj -- "D:\YMConnect\YMConnectDotNet_1_1_10_Windows\YMConnect_CS.dll" > sdk_report.txt
3. Open the text file:
   notepad sdk_report.txt
4. Share its contents (it contains only local SDK type signatures and paths).

Do not set hardware_readonly.json enabled=true yet. The existing bridge's
reflection-based OpenConnection lookup expects exactly two parameters and
may not match the current SDK's optional-parameter overload.
