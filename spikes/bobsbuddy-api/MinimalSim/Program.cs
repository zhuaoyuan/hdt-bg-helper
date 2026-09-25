using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using BobsBuddy;
using BobsBuddy.Simulation;
using BobsBuddy.Utils;
using HearthDb;
using HearthDb.Enums;

namespace MinimalSim
{
	internal static class Program
	{
		// Vanilla 1/1 Beast token; stats are overridden per scenario.
		private const string VanillaCardId = "CFM_315t";

		private static int Main()
		{
			Console.WriteLine($"BobsBuddy {typeof(SimulationRunner).Assembly.GetName().Version}, HearthDb {typeof(Cards).Assembly.GetName().Version}");
			Console.WriteLine($"Process x64: {Environment.Is64BitProcess}, cores: {Environment.ProcessorCount}");

			if(!Cards.All.TryGetValue(VanillaCardId, out var card))
			{
				Console.WriteLine($"HearthDb has no card {VanillaCardId}");
				return 1;
			}
			Console.WriteLine($"Card {VanillaCardId}: {card.Name} {card.Attack}/{card.Health}, SupportedCards={SupportedCards.VerifyCardIsSupported(card)}");

			var ok = true;
			ok &= Run("A: 10/10 vs 1/1 (expect win 100%)", new[] { (10, 10) }, new[] { (1, 1) }, o => o.winRate > 0.999);
			ok &= Run("B: 3/3 vs 3/3 (expect tie 100%)", new[] { (3, 3) }, new[] { (3, 3) }, o => o.tieRate > 0.999);
			ok &= Run("C: 7v7 asymmetric (expect mixed outcome)",
				new[] { (2, 3), (3, 2), (1, 5), (4, 1), (2, 2), (5, 5), (1, 1) },
				new[] { (3, 3), (2, 4), (4, 2), (1, 6), (6, 1), (3, 5), (2, 2) },
				o => Math.Abs(o.winRate + o.tieRate + o.lossRate - 1) < 0.001 && o.winRate < 0.999 && o.lossRate < 0.999);

			Console.WriteLine(ok ? "ALL CHECKS PASSED" : "SOME CHECKS FAILED");
			return ok ? 0 : 2;
		}

		private static bool Run(string name, (int atk, int hp)[] player, (int atk, int hp)[] opponent, Func<Output, bool> check)
		{
			var simulator = new Simulator();
			var input = new Input
			{
				availableRaces = new List<Race> { Race.BEAST, Race.MECHANICAL, Race.DEMON, Race.MURLOC, Race.DRAGON },
			};
			input.SetTurn(3);
			SetupPlayer(simulator, input.Player, player, true);
			SetupPlayer(simulator, input.Opponent, opponent, false);

			var sw = Stopwatch.StartNew();
			var output = new SimulationRunner().SimulateMultiThreaded(input, 10_000, Math.Max(1, Environment.ProcessorCount / 2), 1_500).Result;
			sw.Stop();

			var passed = check(output);
			Console.WriteLine($"{name}: win={output.winRate:P1} tie={output.tieRate:P1} loss={output.lossRate:P1} " +
				$"theirDeath={output.theirDeathRate:P1} myDeath={output.myDeathRate:P1} sims={output.simulationCount} " +
				$"exit={output.myExitCondition} elapsed={sw.ElapsedMilliseconds}ms -> {(passed ? "OK" : "FAIL")}");
			return passed;
		}

		private static void SetupPlayer(Simulator simulator, Player target, (int atk, int hp)[] board, bool friendly)
		{
			target.Health = 30;
			target.Tier = 2;
			var gameId = friendly ? 100 : 200;
			foreach(var (atk, hp) in board)
			{
				var m = simulator.MinionFactory.CreateFromCardId(VanillaCardId, friendly);
				m.baseAttack = atk;
				m.maxAttack = atk;
				m.baseHealth = hp;
				m.maxHealth = hp;
				m.tier = 1;
				m.game_id = gameId++;
				target.Side.Add(m);
			}
		}
	}
}
