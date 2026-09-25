using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;

// Usage: ApiDump <target.dll> <out.txt> [extra reference dirs...]
if (args.Length < 2)
{
	Console.Error.WriteLine("Usage: ApiDump <target.dll> <out.txt> [extra reference dirs...]");
	return 1;
}

var target = Path.GetFullPath(args[0]);
var output = Path.GetFullPath(args[1]);
var refDirs = new List<string> { Path.GetDirectoryName(target)!, RuntimeEnvironment.GetRuntimeDirectory() };
refDirs.AddRange(args.Skip(2));

var paths = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
foreach (var dir in refDirs)
	foreach (var file in Directory.GetFiles(dir, "*.dll"))
		paths.TryAdd(Path.GetFileName(file), file);
paths[Path.GetFileName(target)] = target;

using var mlc = new MetadataLoadContext(new PathAssemblyResolver(paths.Values), "System.Private.CoreLib");
var asm = mlc.LoadFromAssemblyPath(target);

var sb = new StringBuilder();
sb.AppendLine($"# {asm.FullName}");
foreach (var attr in asm.GetCustomAttributesData())
	sb.AppendLine($"# [{attr.AttributeType.Name}({string.Join(", ", attr.ConstructorArguments.Select(a => a.Value))})]");
foreach (var r in asm.GetReferencedAssemblies())
	sb.AppendLine($"# ref {r.FullName}");
sb.AppendLine();

Type[] types;
try { types = asm.GetTypes(); }
catch (ReflectionTypeLoadException e) { types = e.Types.Where(t => t != null).ToArray()!; }

var allTypes = types.Length;
var publicTypes = types.Where(t => t.IsVisible).OrderBy(t => t.FullName, StringComparer.Ordinal).ToList();
sb.AppendLine($"# types: {allTypes} total, {publicTypes.Count} public");
sb.AppendLine();

const BindingFlags Flags = BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;

foreach (var t in publicTypes)
{
	sb.AppendLine($"{Kind(t)} {t.FullName}{BaseInfo(t)}");
	foreach (var c in Safe(() => t.GetConstructors(BindingFlags.Public | BindingFlags.Instance)))
		sb.AppendLine($"  .ctor({Params(c)})");
	if (t.IsEnum)
	{
		sb.AppendLine($"  values: {Safe(() => t.GetFields(BindingFlags.Public | BindingFlags.Static)).Length}");
	}
	else
	{
		foreach (var f in Safe(() => t.GetFields(Flags)))
			sb.AppendLine($"  field {(f.IsStatic ? "static " : "")}{(f.IsInitOnly ? "readonly " : "")}{Name(f.FieldType)} {f.Name}");
		foreach (var p in Safe(() => t.GetProperties(Flags)))
		{
			var get = p.GetMethod is { IsPublic: true } ? "get;" : "";
			var set = p.SetMethod is { IsPublic: true } ? "set;" : "";
			sb.AppendLine($"  prop {Name(p.PropertyType)} {p.Name} {{ {get}{set} }}");
		}
		foreach (var m in Safe(() => t.GetMethods(Flags)).Where(m => !m.IsSpecialName))
			sb.AppendLine($"  method {(m.IsStatic ? "static " : "")}{Name(m.ReturnType)} {m.Name}({Params(m)})");
	}
	sb.AppendLine();
}

Directory.CreateDirectory(Path.GetDirectoryName(output)!);
File.WriteAllText(output, sb.ToString());
Console.WriteLine($"{asm.FullName}: {allTypes} types, {publicTypes.Count} public -> {output}");
return 0;

static T[] Safe<T>(Func<T[]> f)
{
	try { return f(); }
	catch (Exception e) { Console.Error.WriteLine($"warn: {e.GetType().Name}: {e.Message}"); return Array.Empty<T>(); }
}

static string Kind(Type t) => t.IsEnum ? "enum" : t.IsInterface ? "interface" : t.IsValueType ? "struct"
	: t.IsAbstract && t.IsSealed ? "static class" : t.IsAbstract ? "abstract class" : t.IsSealed ? "sealed class" : "class";

static string BaseInfo(Type t)
{
	try
	{
		if (t.IsEnum || t.IsValueType || t.IsInterface || t.BaseType == null || t.BaseType.FullName == "System.Object")
			return "";
		return $" : {Name(t.BaseType)}";
	}
	catch { return " : ?"; }
}

static string Params(MethodBase m)
{
	try { return string.Join(", ", m.GetParameters().Select(p => $"{Name(p.ParameterType)} {p.Name}")); }
	catch { return "?"; }
}

static string Name(Type t)
{
	try
	{
		if (t.IsGenericType)
		{
			var baseName = t.Name.Split('`')[0];
			return $"{baseName}<{string.Join(", ", t.GetGenericArguments().Select(Name))}>";
		}
		if (t.IsArray)
			return Name(t.GetElementType()!) + "[]";
		return t.Name;
	}
	catch { return "?"; }
}
