using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using BobsBuddy;
using BobsBuddy.Simulation;
using HdtDiagLogger;
using HearthDb.Enums;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace DumpTest
{
	internal static class Program
	{
		private const string VanillaCardId = "CFM_315t";

		private static int Main()
		{
			var ok = true;
			ok &= CheckDumper();
			ok &= CheckAnonymizer();
			ok &= CheckWriter();
			Console.WriteLine(ok ? "ALL CHECKS PASSED" : "SOME CHECKS FAILED");
			return ok ? 0 : 2;
		}

		private static bool CheckDumper()
		{
			var simulator = new Simulator();
			var input = new Input { availableRaces = new List<Race> { Race.BEAST, Race.MECHANICAL, Race.DEMON, Race.MURLOC, Race.DRAGON } };
			input.SetTurn(8);
			Setup(simulator, input.Player, true);
			Setup(simulator, input.Opponent, false);

			var before = Dump(input, "input (before simulation)");
			var output = new SimulationRunner().SimulateMultiThreaded(input, 10_000, Math.Max(1, Environment.ProcessorCount / 2), 1_500).Result;
			var after = Dump(input, "input (after simulation)");
			var outDump = Dump(output, "output");

			// same input dumped twice must be identical: dumping must not change state
			var again = new ReflectionDumper().Dump(input).ToString(Formatting.None);
			var stable = again == after.ToString(Formatting.None);
			Console.WriteLine($"repeat dump identical: {stable}");
			Console.WriteLine($"input unchanged by simulation: {before.ToString(Formatting.None) == after.ToString(Formatting.None)}");

			Directory.CreateDirectory("out");
			File.WriteAllText(Path.Combine("out", "input.json"), after.ToString(Formatting.Indented));
			File.WriteAllText(Path.Combine("out", "output.json"), outDump.ToString(Formatting.Indented));
			var skipped = after.SelectTokens("$..['$skipped']").Select(t => (string)t).GroupBy(x => x)
				.Select(g => $"{g.Key} x{g.Count()}");
			Console.WriteLine("skipped types: " + string.Join("; ", skipped));
			var truncated = after.SelectTokens("$..['$truncated']").Select(t => (string)t).Distinct();
			Console.WriteLine("truncated at: " + string.Join("; ", truncated));
			var minion = after.SelectToken("$.Player.Side.items[0]") ?? after.SelectToken("$..Side.items[0]");
			Console.WriteLine("first friendly minion fields: " + string.Join(", ", ((JObject)minion!).Properties().Select(p => p.Name).Take(40)));
			Console.WriteLine($"win={output.winRate:P1} sims={output.simulationCount}");
			return stable;
		}

		private static JToken Dump(object o, string label)
		{
			var d = new ReflectionDumper();
			var sw = Stopwatch.StartNew();
			var json = d.Dump(o);
			var ms = sw.Elapsed.TotalMilliseconds;
			var text = json.ToString(Formatting.None);
			Console.WriteLine($"{label}: {ms:F1} ms, nodes={d.Nodes}, truncated={d.Truncated}, json={text.Length:N0} chars");
			return json;
		}

		private static void Setup(Simulator simulator, Player target, bool friendly)
		{
			target.Health = 30;
			target.Tier = 4;
			var gameId = friendly ? 100 : 200;
			for(var i = 0; i < 7; i++)
			{
				var m = simulator.MinionFactory.CreateFromCardId(VanillaCardId, friendly);
				m.baseAttack = m.maxAttack = 2 + i;
				m.baseHealth = m.maxHealth = 7 - i;
				m.tier = 1;
				m.game_id = gameId++;
				target.Side.Add(m);
			}
		}

		/// <summary>Writes a fake game into out/fake_root for tools/check_capture.py.</summary>
		private static bool CheckWriter()
		{
			var root = Path.GetFullPath(Path.Combine("out", "fake_root"));
			var dir = Path.Combine(root, "20260101_000000_fake01");
			if(Directory.Exists(dir))
				Directory.Delete(dir, true);
			Directory.CreateDirectory(root);
			var anonymizer = new Anonymizer(Path.Combine(root, "salt.txt"));
			var errors = 0;
			var w = new RecordWriter(dir, anonymizer, _ => errors++);
			w.File("meta.json", () => new JObject { ["schemaVersion"] = 1, ["pluginVersion"] = "test", ["endedAt"] = "x", ["lines"] = 3 }.ToString());
			w.Raw(1, 0, "D 00:00:00.0000001 PowerTaskList.DebugPrintPower() - CREATE_GAME");
			w.Raw(2, 5, "D 00:00:00.0000002 PowerTaskList.DebugPrintPower() -     TAG_CHANGE Entity=Tester#1234 tag=RESOURCES value=3");
			w.Raw(3, 9, "D 00:00:00.0000003 PowerTaskList.DebugPrintPower() -     TAG_CHANGE Entity=GameEntity tag=2022 value=0");
			var seq = 0;
			void Rec(string type, JObject body)
			{
				body["seq"] = ++seq;
				body["type"] = type;
				w.Record(() => body.ToString(Formatting.None));
			}
			Rec("combat_phase", new JObject { ["value"] = true });
			Rec("entities", new JObject { ["reason"] = "combat_start", ["context"] = new JObject { ["turn"] = 3 }, ["entityCount"] = 1, ["captureMs"] = 0.5 });
			Rec("hdt_bb", new JObject { ["key"] = 3, ["state"] = "Combat", ["reRunCount"] = 0, ["hasInput"] = true, ["hasOutput"] = true });
			Rec("combat_phase", new JObject { ["value"] = false });
			Rec("entities", new JObject { ["reason"] = "combat_end", ["context"] = new JObject { ["turn"] = 4 }, ["entityCount"] = 1 });
			w.Close(5000);
			var ok = errors == 0 && File.Exists(Path.Combine(dir, "power.log.gz")) && !File.Exists(Path.Combine(dir, "power.log"));
			Console.WriteLine($"writer: {(ok ? "OK" : "FAIL")} ({dir})");
			return ok;
		}

		private static bool CheckAnonymizer()
		{
			var saltFile = Path.Combine(Path.GetTempPath(), "hdtdiag-test-salt.txt");
			var a = new Anonymizer(saltFile);
			a.AddKnownName("小明#51234");
			var cases = new[]
			{
				"D 16:28:12.1 PowerTaskList.DebugPrintPower() -     TAG_CHANGE Entity=小明#51234 tag=RESOURCES value=3",
				"D 16:28:12.1 PowerTaskList.DebugPrintPower() -     Player EntityID=2 PlayerID=1 GameAccountId=[hi=144115198130930503 lo=12345678]",
				"{\"name\":\"小明\",\"other\":\"Some Player#1234\"}",
				"TAG_CHANGE Entity=[entityName=Murloc Tidehunter id=12 zone=PLAY] tag=ATK value=2",
			};
			var ok = true;
			foreach(var c in cases)
			{
				var r = a.Apply(c);
				Console.WriteLine($"  {c}\n  -> {r}");
				ok &= !r.Contains("小明") && !System.Text.RegularExpressions.Regex.IsMatch(r, @"#\d{3,6}") && !r.Contains("12345678");
			}
			ok &= a.Apply(cases[3]) == cases[3];
			ok &= a.Placeholder("小明") == new Anonymizer(saltFile).Placeholder("小明");
			Console.WriteLine($"anonymizer: {(ok ? "OK" : "FAIL")}");
			return ok;
		}
	}
}
