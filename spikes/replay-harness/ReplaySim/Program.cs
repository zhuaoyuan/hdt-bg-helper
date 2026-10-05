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
					Console.Error.WriteLine(
						"Usage: ReplaySim --bb-dir DIR --input FILE [--iterations N] [--threads N] [--max-duration MS] [--perturb Path=Value]...\n" +
						"   or: ReplaySim --bb-dir DIR --batch JOBS.jsonl [--iterations N] [--threads N] [--max-duration MS]");
					return 2;
				}

				var resolveHook = CreateResolver(opts.BbDir);
				AppDomain.CurrentDomain.AssemblyResolve += resolveHook;

				var bbAsm = Assembly.LoadFrom(Path.Combine(opts.BbDir, "BobsBuddy.dll"));
				Assembly.LoadFrom(Path.Combine(opts.BbDir, "BobsBuddy.Common.dll"));
				Assembly.LoadFrom(Path.Combine(opts.BbDir, "HearthDb.dll"));

				var iterations = opts.Iterations ?? 10_000;
				var threads = opts.Threads ?? Math.Max(1, Environment.ProcessorCount / 2);
				var maxDuration = opts.MaxDuration ?? 5_000;

				var simulatorType = bbAsm.GetType("BobsBuddy.Simulation.Simulator", true);
				var runnerType = bbAsm.GetType("BobsBuddy.Simulation.SimulationRunner", true);
				var runner = Activator.CreateInstance(runnerType);
				var simulate = runnerType.GetMethod("SimulateMultiThreaded", BindingFlags.Instance | BindingFlags.Public);
				if(simulate == null)
					throw new MissingMethodException("SimulationRunner.SimulateMultiThreaded");

				var bbVersion = bbAsm.GetName().Version?.ToString();

				if(opts.BatchPath != null)
				{
					RunBatch(opts.BatchPath, bbAsm, simulatorType, runner, simulate, iterations, threads, maxDuration, bbVersion, opts.Perturbations);
					return 0;
				}

				var result = RunOne(bbAsm, simulatorType, runner, simulate, opts.InputPath, null, iterations, threads, maxDuration, bbVersion, opts.Perturbations);
				Console.WriteLine(result.ToString(Formatting.None));
				return result.Value<bool>("ok") ? 0 : 1;
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

		private static void RunBatch(
			string batchPath,
			Assembly bbAsm,
			Type simulatorType,
			object runner,
			MethodInfo simulate,
			int iterations,
			int threads,
			int maxDuration,
			string bbVersion,
			List<KeyValuePair<string, string>> perturbations)
		{
			using var reader = new StreamReader(batchPath);
			string line;
			var lineNo = 0;
			while((line = reader.ReadLine()) != null)
			{
				lineNo++;
				line = line.Trim();
				if(line.Length == 0 || line.StartsWith("#"))
					continue;

				JObject job;
				try
				{
					job = JObject.Parse(line);
				}
				catch(Exception ex)
				{
					WriteJobError(null, "job_parse", ex.Message, lineNo);
					continue;
				}

				var id = job.Value<string>("id");
				try
				{
					string inputPath = job.Value<string>("inputPath");
					JToken inputToken = job["input"];
					string tempPath = null;
					if(inputToken != null && inputToken.Type != JTokenType.Null)
					{
						tempPath = Path.Combine(Path.GetTempPath(), "replaysim-batch-" + Guid.NewGuid().ToString("n") + ".json");
						File.WriteAllText(tempPath, inputToken.ToString(Formatting.None));
						inputPath = tempPath;
					}
					if(string.IsNullOrWhiteSpace(inputPath))
					{
						WriteJobError(id, "missing_input", "need input or inputPath", lineNo);
						continue;
					}

					var jobIter = job["iterations"]?.Value<int?>() ?? iterations;
					var jobThreads = job["threads"]?.Value<int?>() ?? threads;
					var jobMax = job["maxDuration"]?.Value<int?>() ?? maxDuration;
					var result = RunOne(bbAsm, simulatorType, runner, simulate, Path.GetFullPath(inputPath), id, jobIter, jobThreads, jobMax, bbVersion, perturbations);
					Console.WriteLine(result.ToString(Formatting.None));
					if(tempPath != null)
					{
						try { File.Delete(tempPath); } catch { /* ignore */ }
					}
				}
				catch(Exception ex)
				{
					WriteJobError(id, ex.GetType().Name, ex.Message, lineNo);
				}
			}
		}

		private static void WriteJobError(string id, string error, string detail, int lineNo)
		{
			var err = new JObject
			{
				["ok"] = false,
				["id"] = id,
				["error"] = error,
				["detail"] = detail,
				["lineNo"] = lineNo,
			};
			Console.WriteLine(err.ToString(Formatting.None));
		}

		private static JObject RunOne(
			Assembly bbAsm,
			Type simulatorType,
			object runner,
			MethodInfo simulate,
			string inputPath,
			string id,
			int iterations,
			int threads,
			int maxDuration,
			string bbVersion,
			List<KeyValuePair<string, string>> perturbations)
		{
			try
			{
				var json = File.ReadAllText(inputPath);
				var root = JToken.Parse(json);

				var swHydrate = Stopwatch.StartNew();
				var simulator = Activator.CreateInstance(simulatorType);
				var hydrator = new Hydrator(bbAsm, simulator);
				var input = hydrator.HydrateInput(root);
				foreach(var p in perturbations)
					hydrator.ApplyPerturbation(input, p.Key, p.Value);
				swHydrate.Stop();

				var swSim = Stopwatch.StartNew();
				var task = (Task)simulate.Invoke(runner, new object[] { input, iterations, threads, maxDuration });
				task.GetAwaiter().GetResult();
				swSim.Stop();

				var output = task.GetType().GetProperty("Result")?.GetValue(task)
					?? throw new InvalidOperationException("SimulateMultiThreaded returned no Result");

				var result = new JObject
				{
					["ok"] = true,
					["id"] = id,
					["bbVersion"] = bbVersion,
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
				return result;
			}
			catch(Exception ex)
			{
				return new JObject
				{
					["ok"] = false,
					["id"] = id,
					["error"] = ex.GetType().Name + ": " + ex.Message,
					["detail"] = ex.ToString(),
				};
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
			public string BatchPath;
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
						case "--batch": o.BatchPath = Next(); break;
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
				if(string.IsNullOrWhiteSpace(o.BbDir))
					return null;
				if(string.IsNullOrWhiteSpace(o.InputPath) == string.IsNullOrWhiteSpace(o.BatchPath))
					return null; // exactly one of --input / --batch
				o.BbDir = Path.GetFullPath(Environment.ExpandEnvironmentVariables(o.BbDir));
				if(o.InputPath != null)
					o.InputPath = Path.GetFullPath(o.InputPath);
				if(o.BatchPath != null)
					o.BatchPath = Path.GetFullPath(o.BatchPath);
				return o;
			}
		}
	}
}
