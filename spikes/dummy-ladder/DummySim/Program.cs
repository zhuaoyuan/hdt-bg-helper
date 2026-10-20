using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading.Tasks;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace ReplaySim
{
	/// <summary>
	/// Spike: hydrate a real player Input, replace the opponent with N identical vanilla minions, simulate.
	/// </summary>
	internal static class Program
	{
		private const string DefaultCardId = "CFM_315t";

		private static int Main(string[] args)
		{
			try
			{
				var opts = Options.Parse(args);
				if(opts == null)
				{
					Console.Error.WriteLine(
						"Usage: DummySim --bb-dir DIR (--self-test | --batch JOBS.jsonl) [--iterations N] [--threads N] [--max-duration MS] [--card-id ID]");
					return 2;
				}

				AppDomain.CurrentDomain.AssemblyResolve += CreateResolver(opts.BbDir);
				var bbAsm = Assembly.LoadFrom(Path.Combine(opts.BbDir, "BobsBuddy.dll"));
				Assembly.LoadFrom(Path.Combine(opts.BbDir, "BobsBuddy.Common.dll"));
				Assembly.LoadFrom(Path.Combine(opts.BbDir, "HearthDb.dll"));

				var iterations = opts.Iterations ?? 500;
				var threads = opts.Threads ?? Math.Max(1, Environment.ProcessorCount / 2);
				var maxDuration = opts.MaxDuration ?? 5_000;
				var simulatorType = bbAsm.GetType("BobsBuddy.Simulation.Simulator", true);
				var runnerType = bbAsm.GetType("BobsBuddy.Simulation.SimulationRunner", true);
				var runner = Activator.CreateInstance(runnerType);
				var simulate = runnerType.GetMethod("SimulateMultiThreaded", BindingFlags.Instance | BindingFlags.Public);
				if(simulate == null)
					throw new MissingMethodException("SimulationRunner.SimulateMultiThreaded");

				if(opts.SelfTest)
					return SelfTest(bbAsm, simulatorType, runner, simulate, iterations, threads, maxDuration, opts.CardId) ? 0 : 1;

				RunBatch(opts.BatchPath, bbAsm, simulatorType, runner, simulate, iterations, threads, maxDuration, opts.CardId);
				return 0;
			}
			catch(Exception ex)
			{
				Console.WriteLine(new JObject
				{
					["ok"] = false,
					["error"] = ex.GetType().Name + ": " + ex.Message,
				}.ToString(Formatting.None));
				return 1;
			}
		}

		private static bool SelfTest(
			Assembly bbAsm,
			Type simulatorType,
			object runner,
			MethodInfo simulate,
			int iterations,
			int threads,
			int maxDuration,
			string cardId)
		{
			var ok = true;
			ok &= RunVanilla(bbAsm, simulatorType, runner, simulate, iterations, threads, maxDuration, cardId,
				"10 vs 1", 10, 1, o => Rate(o, "winRate") > 0.99);
			ok &= RunVanilla(bbAsm, simulatorType, runner, simulate, iterations, threads, maxDuration, cardId,
				"3 vs 3", 3, 3, o => Rate(o, "tieRate") > 0.99);
			ok &= RunVanilla(bbAsm, simulatorType, runner, simulate, iterations, threads, maxDuration, cardId,
				"1 vs 10", 1, 10, o => Rate(o, "lossRate") > 0.99);
			Console.WriteLine(ok ? "SELF-TEST PASSED" : "SELF-TEST FAILED");
			return ok;
		}

		private static bool RunVanilla(
			Assembly bbAsm,
			Type simulatorType,
			object runner,
			MethodInfo simulate,
			int iterations,
			int threads,
			int maxDuration,
			string cardId,
			string name,
			int playerStat,
			int oppStat,
			Func<object, bool> check)
		{
			var simulator = Activator.CreateInstance(simulatorType);
			var inputType = bbAsm.GetType("BobsBuddy.Simulation.Input", true);
			var input = Activator.CreateInstance(inputType);
			Invoke(input, "SetTurn", 5);
			FillSide(simulator, GetMember(input, "Player"), playerStat, playerStat, 7, cardId, true, 100);
			FillSide(simulator, GetMember(input, "Opponent"), oppStat, oppStat, 7, cardId, false, 200);
			SetInt(GetMember(input, "Player"), "Health", 40);
			SetInt(GetMember(input, "Opponent"), "Health", 40);
			var output = Simulate(runner, simulate, input, iterations, threads, maxDuration);
			var passed = check(output);
			Console.WriteLine(
				$"{name}: win={Rate(output, "winRate"):P1} tie={Rate(output, "tieRate"):P1} loss={Rate(output, "lossRate"):P1} -> {(passed ? "OK" : "FAIL")}");
			return passed;
		}

		private static void RunBatch(
			string batchPath,
			Assembly bbAsm,
			Type simulatorType,
			object runner,
			MethodInfo simulate,
			int iterations,
			int threads,
			int maxDuration,
			string cardId)
		{
			var jobs = new List<JObject>();
			foreach(var line in File.ReadLines(batchPath))
			{
				var trimmed = line.Trim();
				if(trimmed.Length == 0 || trimmed.StartsWith("#"))
					continue;
				jobs.Add(JObject.Parse(trimmed));
			}

			foreach(var group in jobs.GroupBy(j => j.Value<string>("inputPath")))
			{
				JToken root;
				try
				{
					root = JToken.Parse(File.ReadAllText(group.Key));
				}
				catch(Exception ex)
				{
					foreach(var job in group)
						WriteError(job.Value<string>("id"), "read_input", ex.Message);
					continue;
				}

				foreach(var job in group)
				{
					var id = job.Value<string>("id");
					try
					{
						var simulator = Activator.CreateInstance(simulatorType);
						var hydrator = new Hydrator(bbAsm, simulator);
						var input = hydrator.HydrateInput(root);
						var atk = job.Value<int?>("attack") ?? 1;
						var hp = job.Value<int?>("health") ?? atk;
						var count = job.Value<int?>("count") ?? 7;
						// measureSide decides which of the two real boards is kept:
						// "player" (default) replaces Input.Opponent with the dummies and
						// measures the real Player board; "opponent" replaces Input.Player
						// with the dummies and measures the real Opponent board. The output
						// win/tie/loss rates are always the dummy side's (Input.Player's).
						var measureSide = (job.Value<string>("measureSide") ?? "player").Trim().ToLowerInvariant();
						string replaceSide;
						bool dummyFriendly;
						int gameIdBase;
						if(measureSide == "player")
						{
							replaceSide = "Opponent";
							dummyFriendly = false;
							gameIdBase = 8000;
						}
						else if(measureSide == "opponent")
						{
							replaceSide = "Player";
							dummyFriendly = true;
							gameIdBase = 100;
						}
						else
						{
							throw new ArgumentException("measureSide must be \"player\" or \"opponent\", got: " + measureSide);
						}
						var fresh = MakeFreshSide(input, replaceSide);
						FillSide(simulator, fresh, atk, hp, count, cardId, dummyFriendly, gameIdBase);
						SetInt(fresh, "Health", 40);
						SetInt(fresh, "Tier", 1);
						SetMember(input, replaceSide, fresh);
						typeof(Hydrator).GetMethod("WireBoardReferences", BindingFlags.Instance | BindingFlags.NonPublic)
							.Invoke(hydrator, new[] { input });

						var sw = Stopwatch.StartNew();
						var output = Simulate(runner, simulate, input, iterations, threads, maxDuration);
						sw.Stop();
						var result = new JObject
						{
							["ok"] = true,
							["id"] = id,
							["attack"] = atk,
							["health"] = hp,
							["count"] = count,
							["cardId"] = cardId,
							["measureSide"] = measureSide,
							["elapsedMs"] = sw.ElapsedMilliseconds,
							["winRate"] = Rate(output, "winRate"),
							["tieRate"] = Rate(output, "tieRate"),
							["lossRate"] = Rate(output, "lossRate"),
							["simulationCount"] = GetInt(output, "simulationCount"),
							["warnings"] = hydrator.Warnings.Count,
						};
						Console.WriteLine(result.ToString(Formatting.None));
					}
					catch(Exception ex)
					{
						var inner = ex is TargetInvocationException tie && tie.InnerException != null ? tie.InnerException : ex;
						WriteError(id, inner.GetType().Name, inner.Message);
					}
				}
			}
		}

		private static object MakeFreshSide(object input, string sideName)
		{
			var old = GetMember(input, sideName);
			if(old == null)
				throw new InvalidOperationException("hydrated input has no " + sideName);
			var playerType = old.GetType();
			foreach(var ctor in playerType.GetConstructors(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
			{
				var ps = ctor.GetParameters();
				if(ps.Length == 1 && ps[0].ParameterType.IsInstanceOfType(input))
					return ctor.Invoke(new[] { input });
			}
			throw new InvalidOperationException("Player has no (Input) constructor");
		}

		private static void FillSide(object simulator, object player, int atk, int hp, int count, string cardId, bool friendly, int gameIdBase)
		{
			var side = GetMember(player, "Side") as IList;
			if(side == null)
				throw new InvalidOperationException("Player.Side is not a list");
			side.Clear();
			foreach(var name in new[] { "HeroPowers", "Trinkets", "Quests", "Hand", "Secrets", "Objectives" })
			{
				if(GetMember(player, name) is IList list)
					list.Clear();
			}
			var factory = GetMember(simulator, "MinionFactory");
			var create = factory.GetType().GetMethod("CreateFromCardId", new[] { typeof(string), typeof(bool) });
			if(create == null)
				throw new MissingMethodException("MinionFactory.CreateFromCardId");
			for(var i = 0; i < count; i++)
			{
				var minion = create.Invoke(factory, new object[] { cardId, friendly });
				if(minion == null)
					throw new InvalidOperationException("CreateFromCardId returned null for " + cardId);
				SetInt(minion, "baseAttack", atk);
				SetInt(minion, "maxAttack", atk);
				SetInt(minion, "baseHealth", hp);
				SetInt(minion, "maxHealth", hp);
				SetInt(minion, "tier", 1);
				SetInt(minion, "game_id", gameIdBase + i);
				side.Add(minion);
			}
		}

		private static object Simulate(object runner, MethodInfo simulate, object input, int iterations, int threads, int maxDuration)
		{
			var task = (Task)simulate.Invoke(runner, new object[] { input, iterations, threads, maxDuration });
			task.GetAwaiter().GetResult();
			return task.GetType().GetProperty("Result")?.GetValue(task)
				?? throw new InvalidOperationException("no Result");
		}

		private static void WriteError(string id, string error, string detail)
		{
			Console.WriteLine(new JObject
			{
				["ok"] = false,
				["id"] = id,
				["error"] = error,
				["detail"] = detail,
			}.ToString(Formatting.None));
		}

		private static double Rate(object output, string name)
		{
			return GetDouble(output, name) ?? 0;
		}

		private static object GetMember(object obj, string name)
		{
			if(obj == null)
				return null;
			const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
			var prop = obj.GetType().GetProperty(name, flags);
			if(prop != null)
				return prop.GetValue(obj);
			var field = obj.GetType().GetField(name, flags);
			return field?.GetValue(obj);
		}

		private static void SetMember(object obj, string name, object value)
		{
			const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
			var prop = obj.GetType().GetProperty(name, flags);
			if(prop != null && prop.CanWrite)
			{
				prop.SetValue(obj, value);
				return;
			}
			var field = obj.GetType().GetField(name, flags);
			if(field == null)
				throw new MissingMemberException(obj.GetType().FullName, name);
			field.SetValue(obj, value);
		}

		private static void SetInt(object obj, string name, int value)
		{
			const BindingFlags flags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
			var prop = obj.GetType().GetProperty(name, flags);
			if(prop != null && prop.CanWrite)
			{
				prop.SetValue(obj, Convert.ChangeType(value, prop.PropertyType, CultureInfo.InvariantCulture));
				return;
			}
			var field = obj.GetType().GetField(name, flags);
			if(field == null)
				throw new MissingMemberException(obj.GetType().FullName, name);
			field.SetValue(obj, Convert.ChangeType(value, field.FieldType, CultureInfo.InvariantCulture));
		}

		private static void Invoke(object obj, string name, params object[] args)
		{
			var method = obj.GetType().GetMethod(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
			if(method == null)
				throw new MissingMethodException(obj.GetType().FullName, name);
			method.Invoke(obj, args);
		}

		private static double? GetDouble(object obj, string name)
		{
			var v = GetMember(obj, name);
			return v == null ? (double?)null : Convert.ToDouble(v, CultureInfo.InvariantCulture);
		}

		private static int? GetInt(object obj, string name)
		{
			var v = GetMember(obj, name);
			return v == null ? (int?)null : Convert.ToInt32(v, CultureInfo.InvariantCulture);
		}

		private static ResolveEventHandler CreateResolver(string bbDir)
		{
			return (_, args) =>
			{
				var name = new AssemblyName(args.Name).Name + ".dll";
				var path = Path.Combine(bbDir, name);
				return File.Exists(path) ? Assembly.LoadFrom(path) : null;
			};
		}

		private sealed class Options
		{
			public string BbDir;
			public string BatchPath;
			public bool SelfTest;
			public int? Iterations;
			public int? Threads;
			public int? MaxDuration;
			public string CardId = DefaultCardId;

			public static Options Parse(string[] args)
			{
				var opts = new Options();
				for(var i = 0; i < args.Length; i++)
				{
					string Next() => i + 1 < args.Length ? args[++i] : null;
					switch(args[i])
					{
						case "--bb-dir":
							opts.BbDir = Next();
							break;
						case "--batch":
							opts.BatchPath = Next();
							break;
						case "--self-test":
							opts.SelfTest = true;
							break;
						case "--iterations":
							opts.Iterations = int.Parse(Next(), CultureInfo.InvariantCulture);
							break;
						case "--threads":
							opts.Threads = int.Parse(Next(), CultureInfo.InvariantCulture);
							break;
						case "--max-duration":
							opts.MaxDuration = int.Parse(Next(), CultureInfo.InvariantCulture);
							break;
						case "--card-id":
							opts.CardId = Next();
							break;
						default:
							return null;
					}
				}
				if(string.IsNullOrWhiteSpace(opts.BbDir))
					return null;
				if(!opts.SelfTest && string.IsNullOrWhiteSpace(opts.BatchPath))
					return null;
				return opts;
			}
		}
	}
}
