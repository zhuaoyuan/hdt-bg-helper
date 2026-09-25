using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using Hearthstone_Deck_Tracker.Plugins;
using Newtonsoft.Json.Linq;

namespace HdtDiagLogger
{
	/// <summary>
	/// Read-only reflection access to HDT's internal <c>BobsBuddyInvoker</c> instances (Q-002).
	/// Detects when the newest instances change state, re-run count, input or output, and dumps them.
	/// </summary>
	internal sealed class HdtBobsBuddyProbe
	{
		private const BindingFlags Static = BindingFlags.Static | BindingFlags.NonPublic | BindingFlags.Public;
		private const BindingFlags Instance = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;

		private sealed class Observed
		{
			public string State = "";
			public int ReRuns;
			public int InputId;
			public int OutputId;
		}

		private readonly FieldInfo? _instances;
		private readonly FieldInfo? _state;
		private readonly FieldInfo? _reRunCount;
		private readonly FieldInfo? _input;
		private readonly PropertyInfo? _output;

		private readonly Dictionary<string, Observed> _observed = new();
		private List<string> _newestKeys = new();
		private int _cachedCount = -1;

		public string? InitError { get; }
		public int Dumps { get; private set; }

		public HdtBobsBuddyProbe()
		{
			var type = typeof(IPlugin).Assembly.GetType("Hearthstone_Deck_Tracker.BobsBuddy.BobsBuddyInvoker");
			if(type == null)
			{
				InitError = "type Hearthstone_Deck_Tracker.BobsBuddy.BobsBuddyInvoker not found";
				return;
			}
			_instances = type.GetField("_instances", Static);
			_state = type.GetField("_state", Instance);
			_reRunCount = type.GetField("_reRunCount", Instance);
			_input = type.GetField("_input", Instance);
			_output = type.GetProperty("Output", Instance);
			var missing = new[]
			{
				_instances == null ? "_instances" : null, _state == null ? "_state" : null,
				_reRunCount == null ? "_reRunCount" : null, _input == null ? "_input" : null,
				_output == null ? "Output" : null,
			}.Where(x => x != null).ToList();
			if(missing.Count > 0)
			{
				var available = type.GetFields(Static | Instance).Select(f => f.Name)
					.Concat(type.GetProperties(Instance).Select(p => p.Name + "{}"));
				InitError = $"missing members: {string.Join(", ", missing)}; available: {string.Join(", ", available)}";
			}
		}

		public void Reset()
		{
			_observed.Clear();
			_newestKeys.Clear();
			_cachedCount = -1;
		}

		/// <summary>
		/// Checks the two newest instances (the current turn, and the previous one that is validated when shopping starts).
		/// <paramref name="force"/> dumps them even when nothing changed.
		/// </summary>
		public List<JObject> Poll(string reason, bool force)
		{
			var result = new List<JObject>();
			if(InitError != null || _instances!.GetValue(null) is not IDictionary dict)
				return result;

			if(dict.Count != _cachedCount || _newestKeys.Any(k => !dict.Contains(k)))
			{
				_newestKeys = dict.Keys.Cast<string>().OrderBy(TurnOf).Skip(Math.Max(0, dict.Count - 2)).ToList();
				_cachedCount = dict.Count;
			}

			foreach(var key in _newestKeys)
			{
				var invoker = dict[key];
				if(invoker == null)
					continue;
				var now = new Observed
				{
					State = _state!.GetValue(invoker)?.ToString() ?? "",
					ReRuns = (int)(_reRunCount!.GetValue(invoker) ?? 0),
					InputId = IdOf(_input!.GetValue(invoker)),
					OutputId = IdOf(_output!.GetValue(invoker)),
				};
				_observed.TryGetValue(key, out var before);
				var changed = before == null || before.State != now.State || before.ReRuns != now.ReRuns
					|| before.InputId != now.InputId || before.OutputId != now.OutputId;
				if(!changed && !force)
					continue;
				_observed[key] = now;
				result.Add(DumpInvoker(key, invoker, now, before, reason));
			}
			return result;
		}

		private JObject DumpInvoker(string key, object invoker, Observed now, Observed? before, string reason)
		{
			var sw = Stopwatch.StartNew();
			var dumper = new ReflectionDumper();
			JToken dump;
			try
			{
				dump = dumper.Dump(invoker);
			}
			catch(Exception ex)
			{
				dump = new JObject { ["$error"] = ex.ToString() };
			}
			Dumps++;
			return new JObject
			{
				["key"] = TurnOf(key),
				["reason"] = reason,
				["state"] = now.State,
				["reRunCount"] = now.ReRuns,
				["inputChanged"] = before == null || before.InputId != now.InputId,
				["outputChanged"] = before == null || before.OutputId != now.OutputId,
				["hasInput"] = now.InputId != 0,
				["hasOutput"] = now.OutputId != 0,
				["dumpMs"] = sw.Elapsed.TotalMilliseconds,
				["dumpNodes"] = dumper.Nodes,
				["dumpTruncated"] = dumper.Truncated,
				["invoker"] = dump,
			};
		}

		// Keys are "{gameId}_{turn}"; the game id is dropped from records.
		private static int TurnOf(string key) => int.TryParse(key.Substring(key.LastIndexOf('_') + 1), out var t) ? t : -1;

		private static int IdOf(object? o) => o == null ? 0 : RuntimeHelpers.GetHashCode(o) | 1;
	}
}
