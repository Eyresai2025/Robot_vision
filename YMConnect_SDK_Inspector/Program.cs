using System.Reflection;
using System.Runtime.Loader;

// Inspects public .NET metadata only. Does not call OpenConnection or access hardware.
if (args.Length != 1 || !File.Exists(args[0]))
{
    Console.Error.WriteLine("Usage: SDKInspector.exe <full-path-to-YMConnect_CS.dll>");
    return 2;
}

string sdkPath = Path.GetFullPath(args[0]);
Console.WriteLine("SDK path: " + sdkPath);
try
{
    var assembly = AssemblyLoadContext.Default.LoadFromAssemblyPath(sdkPath);
    Console.WriteLine("Assembly: " + assembly.FullName);
    var types = assembly.GetExportedTypes();
    foreach (var type in types.Where(t =>
        t.FullName?.Contains("MotomanController", StringComparison.OrdinalIgnoreCase) == true ||
        t.FullName?.Contains("ControllerState", StringComparison.OrdinalIgnoreCase) == true ||
        t.FullName?.Contains("Variable", StringComparison.OrdinalIgnoreCase) == true &&
          (t.Name.Contains("Byte", StringComparison.OrdinalIgnoreCase) ||
           t.Name.Contains("Integer", StringComparison.OrdinalIgnoreCase) ||
           t.Name.Contains("Variable", StringComparison.OrdinalIgnoreCase))))
    {
        Console.WriteLine("\nTYPE: " + type.FullName);
        foreach (var p in type.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly))
            Console.WriteLine($"  PROP {p.PropertyType.Name} {p.Name}");
        foreach (var m in type.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly)
                 .Where(m => !m.IsSpecialName && (m.Name.Contains("OpenConnection", StringComparison.OrdinalIgnoreCase) ||
                    m.Name.Contains("CloseConnection", StringComparison.OrdinalIgnoreCase) ||
                    m.Name.Contains("Read", StringComparison.OrdinalIgnoreCase) ||
                    m.Name.Contains("Status", StringComparison.OrdinalIgnoreCase))))
        {
            string ps = string.Join(", ", m.GetParameters().Select(p =>
                $"{(p.IsOut ? "out " : "")}{p.ParameterType.Name} {p.Name}{(p.IsOptional ? " [optional]" : "")}"));
            Console.WriteLine($"  METHOD {(m.IsStatic ? "static " : "")}{m.ReturnType.Name} {m.Name}({ps})");
        }
    }
    return 0;
}
catch (ReflectionTypeLoadException e)
{
    Console.Error.WriteLine("Could not load some SDK types:");
    foreach (var error in e.LoaderExceptions.Where(x => x != null))
        Console.Error.WriteLine("  " + error!.Message);
    return 1;
}
catch (Exception e)
{
    Console.Error.WriteLine(e.ToString());
    return 1;
}
