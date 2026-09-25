// Reads metadata of an HDT assembly (type/method names, user-string heap) without loading or decompiling it.
// Usage: MetadataProbe <HearthstoneDeckTracker.exe> <outDir>
// Writes: types.txt, bobsbuddyinvoker_methods.txt, cjk_strings.txt / all_strings.txt (user string + methods whose IL loads it).
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;
using System.Reflection.PortableExecutable;
using System.Text;

var path = args.Length > 0 ? args[0] : @"C:\Program Files\HDT\HearthstoneDeckTracker.exe";
var outDir = args.Length > 1 ? args[1] : "out";
Directory.CreateDirectory(outDir);

using var fs = File.OpenRead(path);
using var pe = new PEReader(fs);
var md = pe.GetMetadataReader();

string TypeName(TypeDefinitionHandle h)
{
    var t = md.GetTypeDefinition(h);
    var name = md.GetString(t.Name);
    var decl = t.GetDeclaringType();
    if (!decl.IsNil)
        return TypeName(decl) + "+" + name;
    var ns = md.GetString(t.Namespace);
    return string.IsNullOrEmpty(ns) ? name : ns + "." + name;
}

var types = new List<string>();
var invokerMethods = new List<string>();
// user-string token -> methods that ldstr it
var stringUsers = new Dictionary<int, SortedSet<string>>();

foreach (var th in md.TypeDefinitions)
{
    var tn = TypeName(th);
    types.Add(tn);
    var td = md.GetTypeDefinition(th);
    foreach (var mh in td.GetMethods())
    {
        var m = md.GetMethodDefinition(mh);
        var mn = md.GetString(m.Name);
        if (tn == "Hearthstone_Deck_Tracker.BobsBuddy.BobsBuddyInvoker")
            invokerMethods.Add($"{mn} (params={m.GetParameters().Count}, attrs={m.Attributes})");
        if (m.RelativeVirtualAddress == 0)
            continue;
        var body = pe.GetMethodBody(m.RelativeVirtualAddress);
        var il = body.GetILBytes();
        if (il == null)
            continue;
        // ldstr = 0x72 followed by a 4-byte user-string token (table 0x70). Naive scan; false positives are
        // possible but only matter if the token also resolves to a CJK string.
        for (var i = 0; i + 4 < il.Length; i++)
        {
            if (il[i] != 0x72 || il[i + 4] != 0x70)
                continue;
            var token = BitConverter.ToInt32(il, i + 1);
            if (!stringUsers.TryGetValue(token, out var set))
                stringUsers[token] = set = new SortedSet<string>();
            set.Add(tn + "::" + mn);
        }
    }
}

static bool HasCjk(string s) => s.Any(c => c >= 0x3000 && c <= 0x9FFF || c >= 0xFF00 && c <= 0xFFEF);

var cjk = new StringBuilder();
var all = new StringBuilder();
var handle = MetadataTokens.UserStringHandle(1);
var heapSize = md.GetHeapSize(HeapIndex.UserString);
var offset = 1;
while (offset < heapSize)
{
    handle = MetadataTokens.UserStringHandle(offset);
    string s;
    try { s = md.GetUserString(handle); }
    catch { break; }
    var token = 0x70000000 | offset;
    var users = stringUsers.TryGetValue(token, out var set) ? string.Join("; ", set) : "(no ldstr found)";
    var line = $"{s.Replace("\r", "\\r").Replace("\n", "\\n")}\t{users}";
    all.AppendLine(line);
    if (HasCjk(s))
        cjk.AppendLine(line);
    offset = MetadataTokens.GetHeapOffset(md.GetNextHandle(handle));
    if (offset <= 0)
        break;
}

File.WriteAllLines(Path.Combine(outDir, "types.txt"), types.OrderBy(x => x, StringComparer.Ordinal));
File.WriteAllLines(Path.Combine(outDir, "bobsbuddyinvoker_methods.txt"), invokerMethods.OrderBy(x => x, StringComparer.Ordinal));
File.WriteAllText(Path.Combine(outDir, "cjk_strings.txt"), cjk.ToString(), Encoding.UTF8);
File.WriteAllText(Path.Combine(outDir, "all_strings.txt"), all.ToString(), Encoding.UTF8);
var asm = md.GetAssemblyDefinition();
Console.WriteLine($"assembly={md.GetString(asm.Name)} version={asm.Version} mvid={md.GetGuid(md.GetModuleDefinition().Mvid)}");
Console.WriteLine($"types={types.Count} invokerMethods={invokerMethods.Count} cjkStrings={cjk.ToString().Split('\n').Length - 1}");
