using System;
using System.Windows.Controls;
using BobsBuddy.Simulation;
using Hearthstone_Deck_Tracker.API;
using Hearthstone_Deck_Tracker.Plugins;
using Hearthstone_Deck_Tracker.Utility.Logging;

namespace HdtPluginSkeleton
{
	public class SkeletonPlugin : IPlugin
	{
		private bool _enabled;

		public string Name => "BG Helper Skeleton";
		public string Description => "Spike: verifies that a plugin builds and loads against the installed HDT.";
		public string ButtonText => "No settings";
		public string Author => "hdt-bg-helper";
		public Version Version => new Version(0, 0, 1);
		public MenuItem MenuItem => null!;

		public void OnLoad()
		{
			_enabled = true;
			var bb = typeof(SimulationRunner).Assembly;
			Log.Info($"[BgHelperSkeleton] loaded; HDT={typeof(IPlugin).Assembly.GetName().Version}, BobsBuddy={bb.GetName().Version} from {bb.Location}");
			GameEvents.OnGameStart.Add(() =>
			{
				if(_enabled)
					Log.Info("[BgHelperSkeleton] game start");
			});
		}

		public void OnUnload() => _enabled = false;

		public void OnButtonPress()
		{
		}

		public void OnUpdate()
		{
		}
	}
}
