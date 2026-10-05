using System;
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
	internal static class Program
	{
		private static int Main(string[] args)
		{
			try
			{
				var opts = Options.Parse(args);
				if(opts == null)
				{
					Console.Error.WriteLine("Usage: ReplaySim --bb-dir DIR --input FILE [--iterations N] [--threads N] [--max-duration MS] [--perturb Path=Value]...");
					return 2;
				}

				var resolveHook = CreateResolver(opts.BbDir);
				AppDomain.CurrentDomain.AssemblyResolve += resolveHook;

				var bbAsm = Assembly.LoadFrom(Path.Combine(opts.BbDir, "BobsBuddy.dll"));
				Assembly.LoadFrom(Path.Combine(opts.BbDir, "BobsBuddy.Common.dll"));
				Assembly.LoadFrom(Path.Combine(opts.BbDir, "HearthDb.dll"));

				var json = File.ReadAllText(opts.InputPath);
				var root = JToken.Parse(json);

				var swHydrate = Stopwatch.StartNew();
				var simulatorType = bbAsm.GetType("BobsBuddy.Simulation.Simulator", true);
				var simulator = Activator.CreateInstance(simulatorType);
				var hydrator = new Hydrator(bbAsm, simulator);
				var input = hydrator.HydrateInput(root);
				foreach(var p in opts.Perturbations)
					hydrator.ApplyPerturbation(input, p.Key, p.Value);
				swHydrate.Stop();

				var iterations = opts.Iterations ?? 10_000;
				var threads = opts.Threads ?? Math.Max(1, Environment.ProcessorCount / 2);
				var maxDuration = opts.MaxDuration ?? 5_000;

				var runnerType = bbAsm.GetType("BobsBuddy.Simulation.SimulationRunner", true);
				var runner = Activator.CreateInstance(runnerType);
				var simulate = runnerType.GetMethod("SimulateMultiThreaded", BindingFlags.Instance | BindingFlags.Public);
				if(simulate == null)
					throw new MissingMethodException("SimulationRunner.SimulateMultiThreaded");

				var swSim = Stopwatch.StartNew();
				var task = (Task)simulate.Invoke(runner, new object[] { input, iterations, threads, maxDuration });
				task.GetAwaiter().GetResult();
				swSim.Stop();

				var output = task.GetType().GetProperty("Result")?.GetValue(task)
					?? throw new InvalidOperationException("SimulateMultiThreaded returned no Result");

				var result = new JObject
				{
					["ok"] = true,
					["bbVersion"] = bbAsm.GetName().Version?.ToString(),
					["hydrateMs"] = swHydrate.ElapsedMilliseconds,
					["elapsedMs"] = swSim.ElapsedMilliseconds,
					["iterationsRequested"] = iterations,
					["threads"] = threads,
					["maxDuration"] = maxDuration,
					["winRate"] = GetDouble(output, "winRate"),
					["tieRate"] = GetDouble(output, "tieRate"),
					["lossRate"] = GetDouble(output, "lossRate"),
					["myDeathRate"] = GetDouble(output, "myDeathRate"),
					["theirDeathRate"] = GetDouble(output, "theirDeathRate"),
					["avDamage"] = GetDouble(output, "avDamage"),
					["medianDamage"] = GetDouble(output, "medianDamage"),
					["simulationCount"] = GetInt(output, "simulationCount"),
					["myExitCondition"] = GetString(output, "myExitCondition"),
					["hydrateWarnings"] = new JArray(hydrator.Warnings),
				};
				Console.WriteLine(result.ToString(Formatting.None));
				return 0;
			}
			catch(Exception ex)
			{
				var err = new JObject
				{
					["ok"] = false,
					["error"] = ex.GetType().Name + ": " + ex.Message,
					["detail"] = ex.ToString(),
				};
				Console.WriteLine(err.ToString(Formatting.None));
				return 1;
			}
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

		private static double? GetDouble(object obj, string name)
		{
			var v = obj.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(obj)
				?? obj.GetType().GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(obj);
			return v == null ? (double?)null : Convert.ToDouble(v, CultureInfo.InvariantCulture);
		}

		private static int? GetInt(object obj, string name)
		{
			var v = obj.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(obj)
				?? obj.GetType().GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(obj);
			return v == null ? (int?)null : Convert.ToInt32(v, CultureInfo.InvariantCulture);
		}

		private static string GetString(object obj, string name)
		{
			var v = obj.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(obj)
				?? obj.GetType().GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(obj);
			return v?.ToString();
		}

		private sealed class Options
		{
			public string BbDir;
			public string InputPath;
			public int? Iterations;
			public int? Threads;
			public int? MaxDuration;
			public readonly List<KeyValuePair<string, string>> Perturbations = new();

			public static Options Parse(string[] args)
			{
				var o = new Options();
				for(var i = 0; i < args.Length; i++)
				{
					string Next() => i + 1 < args.Length ? args[++i] : null;
					switch(args[i])
					{
						case "--bb-dir": o.BbDir = Next(); break;
						case "--input": o.InputPath = Next(); break;
						case "--iterations": o.Iterations = int.Parse(Next(), CultureInfo.InvariantCulture); break;
						case "--threads": o.Threads = int.Parse(Next(), CultureInfo.InvariantCulture); break;
						case "--max-duration": o.MaxDuration = int.Parse(Next(), CultureInfo.InvariantCulture); break;
						case "--perturb":
							var raw = Next();
							var eq = raw?.IndexOf('=') ?? -1;
							if(eq <= 0) return null;
							o.Perturbations.Add(new KeyValuePair<string, string>(raw.Substring(0, eq), raw.Substring(eq + 1)));
							break;
						default: return null;
					}
				}
				if(string.IsNullOrWhiteSpace(o.BbDir) || string.IsNullOrWhiteSpace(o.InputPath))
					return null;
				o.BbDir = Path.GetFullPath(Environment.ExpandEnvironmentVariables(o.BbDir));
				o.InputPath = Path.GetFullPath(o.InputPath);
				return o;
			}
		}
	}
}
