using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Windows.Controls;
using BobsBuddy.Simulation;
using Hearthstone_Deck_Tracker.API;
using Hearthstone_Deck_Tracker.Enums;
using Hearthstone_Deck_Tracker.Hearthstone;
using Hearthstone_Deck_Tracker.Plugins;
using Hearthstone_Deck_Tracker.Utility.Logging;
using Newtonsoft.Json.Linq;

namespace HdtDiagLogger
{
	public class DiagPlugin : IPlugin
	{
		private const string LogPrefix = "[BgHelperDiag]";
		private const int PreGameBufferLines = 5000;

		private readonly Queue<string> _preGameLines = new();
		private bool _enabled;
		private bool _processExitHooked;
		private string _root = "";
		private Anonymizer? _anonymizer;
		private HdtBobsBuddyProbe? _probe;
		private GameSession? _session;

		public string Name => "BG Helper Diagnostic Logger";
		public string Description => "Spike (hdt-bg-helper): records Battlegrounds games as completely as possible for offline analysis. "
			+ "Records are stored locally under %APPDATA%\\HearthstoneDeckTracker\\BgHelperDiag and BattleTags are anonymised.";
		public string ButtonText => "Open records folder";
		public string Author => "hdt-bg-helper";
		public Version Version => new(0, 1, 0);
		public MenuItem MenuItem => null!;

		public void OnLoad()
		{
			_enabled = true;
			_root = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "HearthstoneDeckTracker", "BgHelperDiag");
			Directory.CreateDirectory(_root);
			_anonymizer = new Anonymizer(Path.Combine(_root, "salt.txt"));
			_probe = new HdtBobsBuddyProbe();
			var bb = typeof(SimulationRunner).Assembly;
			Log.Info($"{LogPrefix} loaded {Version}; HDT={typeof(IPlugin).Assembly.GetName().Version}, BobsBuddy={bb.GetName().Version}; records: {_root}");
			if(_probe.InitError != null)
				Log.Warn($"{LogPrefix} BobsBuddyInvoker probe unavailable: {_probe.InitError}");

			// ActionList.Add attributes handlers to the plugin by the calling method's type, so these calls must stay
			// directly in this method: otherwise HDT keeps invoking them after the plugin is disabled.
			LogEvents.OnPowerLogLine.Add(OnPowerLine);
			GameEvents.OnGameStart.Add(OnGameStart);
			GameEvents.OnGameEnd.Add(OnGameEnd);
			GameEvents.OnInMenu.Add(() => Event("in_menu", new JObject()));
			GameEvents.OnTurnStart.Add(p => Event("turn_start", new JObject { ["activePlayer"] = p.ToString(), ["turn"] = Core.Game.GetTurnNumber() }));
			GameEvents.OnOpponentSecretTriggered.Add(c => Event("opponent_secret_triggered", new JObject { ["cardId"] = c?.Id }));
			GameEvents.OnPlayerMinionAttack.Add(a => Event("player_minion_attack", Attack(a)));
			GameEvents.OnOpponentMinionAttack.Add(a => Event("opponent_minion_attack", Attack(a)));

			if(!_processExitHooked)
			{
				_processExitHooked = true;
				AppDomain.CurrentDomain.ProcessExit += (_, _) => _session?.EndAndWait("process_exit", 3000);
			}

			if(Core.Game.IsRunning && Core.Game.IsBattlegroundsMatch)
				StartSession("enabled_mid_game");
		}

		public void OnUnload()
		{
			_enabled = false;
			_session?.EndAndWait("plugin_unload", 3000);
			_session = null;
			_preGameLines.Clear();
		}

		public void OnButtonPress()
		{
			try
			{
				System.Diagnostics.Process.Start("explorer.exe", _root);
			}
			catch(Exception ex)
			{
				Log.Error($"{LogPrefix} {ex}");
			}
		}

		public void OnUpdate()
		{
			if(_enabled)
				_session?.OnUpdate();
		}

		private void OnPowerLine(string line)
		{
			if(!_enabled)
				return;
			if(_session != null)
			{
				_session.OnLine(line);
				return;
			}
			_preGameLines.Enqueue(line);
			while(_preGameLines.Count > PreGameBufferLines)
				_preGameLines.Dequeue();
		}

		private void OnGameStart()
		{
			if(!_enabled)
				return;
			try
			{
				_session?.End("next_game_start");
				_session = null;
				var game = Core.Game;
				// The game type comes from HearthMirror and can still be unknown here; unknown games are recorded and
				// flagged in meta.json at the end.
				if(game.IsBattlegroundsMatch || game.CurrentGameType.ToString() == "GT_UNKNOWN")
					StartSession("game_start");
				else
					_preGameLines.Clear();
			}
			catch(Exception ex)
			{
				Log.Error($"{LogPrefix} game start: {ex}");
			}
		}

		private void StartSession(string reason)
		{
			_session = new GameSession(_root, _anonymizer!, _probe!, Version);
			Log.Info($"{LogPrefix} recording ({reason}) to {_session.Directory}");
			_session.Event("session_start", new JObject { ["reason"] = reason });

			// Power lines can arrive before the loading-screen line that triggers OnGameStart.
			var buffered = _preGameLines.ToList();
			_preGameLines.Clear();
			var start = buffered.FindLastIndex(l => l.Contains("CREATE_GAME"));
			if(start >= 0)
			{
				_session.Event("replay_buffered_lines", new JObject { ["count"] = buffered.Count - start });
				foreach(var l in buffered.Skip(start))
					_session.OnLine(l);
			}
		}

		private void OnGameEnd()
		{
			if(!_enabled || _session == null)
				return;
			try
			{
				_session.End("game_end");
				Log.Info($"{LogPrefix} finished {_session.Directory}");
			}
			catch(Exception ex)
			{
				Log.Error($"{LogPrefix} game end: {ex}");
			}
			_session = null;
		}

		private void Event(string name, JObject data)
		{
			if(_enabled)
				_session?.Event(name, data);
		}

		private static JObject Attack(AttackInfo? a) => new()
		{
			["attacker"] = a?.Attacker?.Id,
			["defender"] = a?.Defender?.Id,
		};
	}
}
