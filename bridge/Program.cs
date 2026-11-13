// EyRes QC+ Robot Vision - YMConnect 1.1.10 read-only bridge.
// Uses reflection so the proprietary vendor DLL is NOT redistributed.
// Exposes only OpenConnection, Status.ReadState, Variables Byte/Integer.Read and CloseConnection.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;

static class Bridge
{
    static readonly JsonSerializerOptions Json = new() { WriteIndented = false };
    static void Emit(object value) { Console.WriteLine(JsonSerializer.Serialize(value, Json)); Console.Out.Flush(); }
    static object? Prop(object? value, string name)
    {
        if (value == null) return null;
        const BindingFlags flags = BindingFlags.Public | BindingFlags.Instance;
        var type = value.GetType();
        return type.GetProperty(name, flags)?.GetValue(value)
            ?? type.GetField(name, flags)?.GetValue(value);
    }
    static string Display(object? value) => value?.ToString() ?? "null";
    static string DescribeError(Exception error) => (error is TargetInvocationException && error.InnerException != null ? error.InnerException : error).Message;
    static object? StatusCode(object? status) => Prop(status, "StatusCode") ?? Prop(status, "Code");
    static bool? StatusSuccess(object? status)
    {
        var code = StatusCode(status);
        if (code == null) return null; // Never treat missing code as successful.
        try { return Convert.ToInt64(code) == 0; }
        catch { return null; }
    }
    static MethodInfo? ExactMethod(Type type, string name, int args) => type.GetMethods(BindingFlags.Public | BindingFlags.Instance)
        .FirstOrDefault(m => m.Name == name && m.GetParameters().Length == args);
    static object? InvokeRead(object target, string methodName, out object? status)
    {
        var method = target.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .FirstOrDefault(m => m.Name == methodName && m.GetParameters().Length == 1 && m.GetParameters()[0].IsOut);
        if (method == null) throw new MissingMethodException(target.GetType().FullName, methodName + "(out data)");
        var args = new object?[] { null };
        status = method.Invoke(target, args);
        return args[0];
    }
    static object? ReadVariable(object controller, string variable, out string outcome)
    {
        outcome = "not_read";
        var match = Regex.Match(variable, @"^([BI])(\d{1,4})$", RegexOptions.IgnoreCase);
        if (!match.Success) { outcome = "invalid_reference"; return null; }
        var variables = Prop(controller, "Variables");
        if (variables == null) { outcome = "Variables property unavailable"; return null; }
        var groupName = match.Groups[1].Value.Equals("B", StringComparison.OrdinalIgnoreCase) ? "Byte" : "Integer";
        var group = Prop(variables, groupName);
        if (group == null) { outcome = "Missing Variables." + groupName + " public property/field; inspect SDK"; return null; }
        var method = group.GetType().GetMethods(BindingFlags.Public | BindingFlags.Instance)
            .FirstOrDefault(m => m.Name == "Read" && m.GetParameters().Length == 2 &&
                m.GetParameters()[0].ParameterType == typeof(ushort) && m.GetParameters()[1].IsOut);
        if (method == null) { outcome = "Missing Read(ushort, out data)"; return null; }
        var args = new object?[] { ushort.Parse(match.Groups[2].Value), null };
        try
        {
            var status = method.Invoke(group, args);
            var ok = StatusSuccess(status);
            outcome = ok == true ? "ok" : ok == false ? "sdk_error:" + Display(StatusCode(status)) : "unverified_status:" + Display(status);
            return ok == true ? Prop(args[1], "Value") : null; // Return primitive, not a whole SDK object.
        }
        catch (Exception e) { outcome = "read_error:" + DescribeError(e); return null; }
    }
    static void Inspect(Assembly assembly)
    {
        foreach (var typename in new[] { "YMConnect.MotomanController", "YMConnect.ControllerStateInterface", "YMConnect.VariablesInterface", "YMConnect.ByteVariableInterface", "YMConnect.IntegerVariableInterface", "YMConnect.StatusInfo" })
        {
            var t = assembly.GetType(typename);
            Emit(new { kind = "sdk_type", name = typename, exists = t != null,
                properties = t?.GetProperties(BindingFlags.Public | BindingFlags.Instance).Select(p => p.Name + ":" + p.PropertyType.Name).ToArray(),
                fields = t?.GetFields(BindingFlags.Public | BindingFlags.Instance).Select(f => f.Name + ":" + f.FieldType.Name).ToArray(),
                methods = t?.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static)
                    .Where(m => m.DeclaringType == t && (m.Name == "OpenConnection" || m.Name == "ReadState" || m.Name == "Read" || m.Name == "CloseConnection"))
                    .Select(m => m.ToString()).ToArray() });
        }
    }
    static int Main(string[] args)
    {
        bool inspect = args.Contains("--inspect", StringComparer.OrdinalIgnoreCase);
        string ip = "", sdk = "", reads = "";
        int interval = 1000;
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i] == "--inspect") continue;
            if (i + 1 >= args.Length) { Emit(new { kind = "error", message = "Missing value for " + args[i] }); return 2; }
            switch (args[i])
            {
                case "--ip": ip = args[++i]; break;
                case "--sdk": sdk = args[++i]; break;
                case "--reads": reads = args[++i]; break;
                case "--interval": if (!int.TryParse(args[++i], out interval)) interval = 1000; break;
                default: Emit(new { kind = "error", message = "Unknown option: " + args[i] }); return 2;
            }
        }
        interval = Math.Clamp(interval, 250, 10000);
        if (!inspect && (!IPAddress.TryParse(ip, out var ipaddr) || ipaddr.AddressFamily != AddressFamily.InterNetwork))
        { Emit(new { kind = "error", message = "Expected --ip valid IPv4 [--sdk path] [--reads B010,I011] [--interval 1000]. Or use --inspect --sdk path without network access." }); return 2; }
        object? controller = null;
        try
        {
            if (string.IsNullOrWhiteSpace(sdk) || !File.Exists(sdk)) throw new FileNotFoundException("YMConnect managed SDK DLL not found", sdk);
            var assembly = Assembly.LoadFrom(Path.GetFullPath(sdk));
            if (inspect)
            {
                Emit(new { kind = "sdk_loaded", assembly = assembly.FullName, network_access = false });
                Inspect(assembly);
                return 0;
            }
            var type = assembly.GetType("YMConnect.MotomanController", throwOnError: true)!;
            var open = type.GetMethods(BindingFlags.Public | BindingFlags.Static)
                .FirstOrDefault(m => m.Name == "OpenConnection" && m.GetParameters().Length == 5 &&
                    m.GetParameters()[0].ParameterType == typeof(string) && m.GetParameters()[1].IsOut);
            if (open == null) throw new MissingMethodException("Expected OpenConnection(string, out StatusInfo, int, int, bool) in YMConnect v1.1.10");
            var openArgs = new object?[] { ip, null, Type.Missing, Type.Missing, Type.Missing };
            var sw = Stopwatch.StartNew();
            controller = open.Invoke(null, openArgs);
            sw.Stop();
            var openStatus = openArgs[1];
            if (controller == null || StatusSuccess(openStatus) == false)
                throw new InvalidOperationException("YMConnect OpenConnection failed: " + Display(openStatus) + " code=" + Display(StatusCode(openStatus)));
            Emit(new { kind = "connected", ip, connection_ms = Math.Round(sw.Elapsed.TotalMilliseconds, 2), status = Display(openStatus), sdk_version = assembly.GetName().Version?.ToString(), status_verified = StatusSuccess(openStatus) == true });
            // Status property and ReadState(out ControllerStateData) confirmed by v1.1.10 SDK report.
            var statusInterface = Prop(controller, "Status") ?? throw new MissingMemberException("MotomanController.Status missing");
            while (true)
            {
                sw.Restart();
                object? stateData = null, stateStatus = null;
                string? stateError = null;
                try { stateData = InvokeRead(statusInterface, "ReadState", out stateStatus); }
                catch (Exception e) { stateError = DescribeError(e); }
                var ok = StatusSuccess(stateStatus);
                var state = ok == true && stateData != null ? new
                {
                    cycle_mode = Display(Prop(stateData, "CycleMode")),
                    is_running = Prop(stateData, "IsRunning"),
                    control_mode = Display(Prop(stateData, "ControlMode")),
                    is_in_hold = Prop(stateData, "IsInHold"),
                    is_alarming = Prop(stateData, "IsAlarming"),
                    is_erroring = Prop(stateData, "IsErroring"),
                    is_servo_on = Prop(stateData, "IsServoOn")
                } : null;
                var values = new Dictionary<string, object?>();
                var variableResults = new Dictionary<string, string>();
                foreach (var variable in reads.Split(',', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries)
                    .Where(s => Regex.IsMatch(s, @"^[BI]\d{1,4}$", RegexOptions.IgnoreCase)).Distinct(StringComparer.OrdinalIgnoreCase).Take(24))
                {
                    values[variable] = ReadVariable(controller, variable, out string result);
                    variableResults[variable] = result;
                }
                sw.Stop();
                Emit(new { kind = "sample", ip, elapsed_ms = Math.Round(sw.Elapsed.TotalMilliseconds, 2),
                    status_read_supported = stateError == null, status_code = Display(StatusCode(stateStatus)),
                    status_verified = ok == true, status = state, status_error = stateError,
                    variables = values, variable_results = variableResults, measured_at = DateTimeOffset.Now.ToString("O") });
                Thread.Sleep(interval);
            }
        }
        catch (Exception ex) { Emit(new { kind = "error", ip, message = DescribeError(ex) }); return 1; }
        finally
        {
            if (controller != null)
            {
                try { ExactMethod(controller.GetType(), "CloseConnection", 0)?.Invoke(controller, null); } catch { }
            }
        }
    }
}
