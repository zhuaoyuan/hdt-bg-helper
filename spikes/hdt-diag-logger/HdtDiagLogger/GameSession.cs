using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text.RegularExpressions;
using System.Threading;
using BobsBuddy.Simulation;
using Hearthstone_Deck_Tracker.Plugins;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using Core = Hearthstone_Deck_Tracker.API.Core;

namespace HdtDiagLogger
{
	/// <summary>Everything recorded for one game. All public methods are called on HDT's thread.</summary>
	internal sealed class GameSession
	{
		public const int SchemaVersion = 1;
		private const int MaxErrors = 100;

		// Single-player combat starts when tag 2022 goes 1 -> 0, duos when 3533 does (facts/bobsbuddy-simulator-input.md 5.1)
		private static readonly Regex CombatTag = new(@"TAG_CHANGE Entity=(?<entity>.+?) tag=(?<tag>2022|3533) value=(?<value>\d+)", RegexOptions.Compiled);

		private readonly RecordWriter _writer;
		private readonly Anonymizer _anonymizer;
		private readonly HdtBobsBuddyProbe _probe;
		private readonly Stopwatch _clock = Stopwatch.StartNew();
		private readonly PerfStats _perf = new();
		private readonly JObject _meta;
		private readonly string _dir;

		private long _lineSeq;
		private long _recordSeq;
		private int _errors;
		private int _writerErrors;
		private bool _ended;
		private bool _combatPhase;
		private int _lineThreadId = -1;
		private long _lastPerfMs;
		private readonly Dictionary<string, int> _counts = new();

		public bool Disabled { get; private set; }
		public string Directory => _dir;

		public GameSession(string rootDir, Anonymizer anonymizer, HdtBobsBuddyProbe probe, Version pluginVersion)
		{
			_anonymizer = anonymizer;
			_probe = probe;
			_probe.Reset();
			_dir = Path.Combine(rootDir, $"{DateTime.Now:yyyyMMdd_HHmmss}_{Guid.NewGuid().ToString("N").Substring(0, 6)}");
			_writer = new RecordWriter(_dir, anonymizer, WriterError);

			var game = Core.Game;
			_meta = new JObject
			{
				["schemaVersion"] = SchemaVersion,
				["pluginVersion"] = pluginVersion.ToString(),
				["startedAt"] = DateTimeOffset.Now.ToString("o"),
				["hdt"] = AssemblyInfo(typeof(IPlugin).Assembly),
				["bobsBuddy"] = AssemblyInfo(typeof(SimulationRunner).Assembly),
				["hearthDb"] = AssemblyInfo(typeof(HearthDb.Cards).Assembly),
				["hearthstoneBuild"] = game.MetaData.HearthstoneBuild,
				["gameTypeAtStart"] = game.CurrentGameType.ToString(),
				["probeInitError"] = probe.InitError,
			};
			var initialMeta = (JObject)_meta.DeepClone();
			_writer.File("meta.json", () => initialMeta.ToString(Formatting.Indented));
			_combatPhase = game.IsBattlegroundsCombatPhase;
			AddNames(game.Player?.Name);
		}

		public void OnLine(string line)
		{
			if(Disabled)
				return;
			var sw = Stopwatch.StartNew();
			try
			{
				_lineThreadId = Environment.CurrentManagedThreadId;
				var seq = ++_lineSeq;
				_writer.Raw(seq, _clock.ElapsedMilliseconds, line);

				if(line.IndexOf("CREATE_GAME", StringComparison.Ordinal) >= 0)
					Record("create_game", new JObject());

				if(line.IndexOf("TAG_CHANGE", StringComparison.Ordinal) >= 0 && CombatTag.Match(line) is { Success: true } m)
					Record("combat_tag", new JObject { ["tag"] = int.Parse(m.Groups["tag"].Value), ["value"] = int.Parse(m.Groups["value"].Value), ["entity"] = m.Groups["entity"].Value });

				var phase = Core.Game.IsBattlegroundsCombatPhase;
				if(phase != _combatPhase)
				{
					_combatPhase = phase;
					Record("combat_phase", new JObject { ["value"] = phase });
					Entities(phase ? "combat_start" : "combat_end");
					PollBobsBuddy(phase ? "combat_start" : "combat_end", force: true);
				}
				else
					PollBobsBuddy("line", force: false);
			}
			catch(Exception ex)
			{
				Error("line", ex);
			}
			_perf.Add("line", sw);
		}

		public void OnUpdate()
		{
			if(Disabled)
				return;
			var sw = Stopwatch.StartNew();
			try
			{
				// Only touch HDT state from the thread that processes log lines (see design 3.3).
				if(Environment.CurrentManagedThreadId == _lineThreadId)
					PollBobsBuddy("update", force: false);
				if(_clock.ElapsedMilliseconds - _lastPerfMs > 5 * 60_000)
					Perf("periodic");
			}
			catch(Exception ex)
			{
				Error("update", ex);
			}
			_perf.Add("update", sw);
		}

		public void Event(string name, JObject data)
		{
			if(Disabled)
				return;
			try
			{
				data["name"] = name;
				Record("event", data);
			}
			catch(Exception ex)
			{
				Error("event", ex);
			}
		}

		public void End(string reason)
		{
			if(_ended)
				return;
			_ended = true;
			try
			{
				if(!Disabled)
				{
					Entities("game_end");
					PollBobsBuddy("game_end", force: true);
				}
				Perf("final");
				var game = Core.Game;
				_meta["endedAt"] = DateTimeOffset.Now.ToString("o");
				_meta["endReason"] = reason;
				_meta["gameTypeAtEnd"] = game.CurrentGameType.ToString();
				_meta["isBattlegroundsMatch"] = game.IsBattlegroundsMatch;
				_meta["isBattlegroundsDuosMatch"] = game.IsBattlegroundsDuosMatch;
				_meta["lines"] = _lineSeq;
				_meta["records"] = _recordSeq;
				_meta["recordCounts"] = JObject.FromObject(_counts);
				_meta["hdtBobsBuddyDumps"] = _probe.Dumps;
				_meta["errors"] = _errors;
				_meta["writerErrors"] = _writerErrors;
				_meta["disabled"] = Disabled;
				var meta = (JObject)_meta.DeepClone();
				_writer.File("meta.json", () => meta.ToString(Formatting.Indented));
			}
			catch(Exception ex)
			{
				Error("end", ex);
			}
			_writer.Close(0);
		}

		/// <summary>Waits for the writer to finish; used when HDT disables the plugin or shuts down.</summary>
		public void EndAndWait(string reason, int waitMs)
		{
			End(reason);
			_writer.Close(waitMs);
		}

		private void Entities(string reason)
		{
			var sw = Stopwatch.StartNew();
			var snap = EntitySnapshot.Capture();
			foreach(var name in snap.PlayerNames)
				AddNames(name);
			_perf.Add("entities", sw);
			var captureMs = snap.CaptureMs;
			RecordLazy("entities", () =>
			{
				var json = snap.ToJson();
				json["reason"] = reason;
				json["captureMs"] = captureMs;
				return json;
			});
		}

		private void PollBobsBuddy(string reason, bool force)
		{
			var sw = Stopwatch.StartNew();
			var dumps = _probe.Poll(reason, force);
			foreach(var dump in dumps)
				Record("hdt_bb", dump);
			_perf.Add(dumps.Count > 0 ? "hdt_bb_dump" : "hdt_bb_poll", sw);
		}

		private void Perf(string reason)
		{
			_lastPerfMs = _clock.ElapsedMilliseconds;
			Record("perf", new JObject
			{
				["reason"] = reason,
				["stats"] = _perf.ToJson(),
				["writerQueue"] = _writer.QueueLength,
				["bytesWritten"] = _writer.BytesWritten,
			});
		}

		private void AddNames(string? name) => _anonymizer.AddKnownName(name);

		private void Record(string type, JObject data) => RecordLazy(type, () => data);

		/// <summary><paramref name="build"/> runs on the writer thread.</summary>
		private void RecordLazy(string type, Func<JObject> build)
		{
			var seq = ++_recordSeq;
			var lineSeq = _lineSeq;
			var ms = _clock.ElapsedMilliseconds;
			_counts[type] = _counts.TryGetValue(type, out var c) ? c + 1 : 1;
			_writer.Record(() =>
			{
				var body = build();
				var head = new JObject { ["seq"] = seq, ["lineSeq"] = lineSeq, ["ms"] = ms, ["type"] = type };
				head.Merge(body);
				return head.ToString(Formatting.None);
			});
		}

		private void Error(string where, Exception ex)
		{
			_errors++;
			if(_errors <= 20)
				Record("error", new JObject { ["where"] = where, ["exception"] = ex.ToString() });
			if(_errors >= MaxErrors && !Disabled)
			{
				Disabled = true;
				Record("error", new JObject { ["where"] = "session", ["exception"] = $"disabled after {_errors} errors" });
			}
		}

		// Runs on the writer thread: must not touch the HDT-thread counters above.
		private void WriterError(Exception ex)
		{
			var n = Interlocked.Increment(ref _writerErrors);
			if(n <= 20)
			{
				var text = ex.ToString();
				_writer.Record(() => new JObject { ["type"] = "writer_error", ["exception"] = text }.ToString(Formatting.None));
			}
		}

		private static JObject AssemblyInfo(System.Reflection.Assembly a)
		{
			var location = a.Location;
			return new JObject
			{
				["version"] = a.GetName().Version?.ToString(),
				["fileVersion"] = string.IsNullOrEmpty(location) ? null : FileVersionInfo.GetVersionInfo(location).FileVersion,
				["directory"] = string.IsNullOrEmpty(location) ? null : Path.GetFileName(Path.GetDirectoryName(location)),
			};
		}
	}
}
