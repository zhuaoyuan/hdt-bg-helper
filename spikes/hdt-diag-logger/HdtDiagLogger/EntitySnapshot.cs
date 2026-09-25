using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Reflection;
using HearthDb.Enums;
using Hearthstone_Deck_Tracker.Hearthstone;
using Hearthstone_Deck_Tracker.Hearthstone.Entities;
using Newtonsoft.Json.Linq;
using Core = Hearthstone_Deck_Tracker.API.Core;

namespace HdtDiagLogger
{
	/// <summary>
	/// Copy of every entity in <c>Core.Game.Entities</c>. <see cref="Capture"/> runs on HDT's thread and only copies
	/// plain values; <see cref="ToJson"/> runs on the writer thread.
	/// </summary>
	internal sealed class EntitySnapshot
	{
		private sealed class EntityCopy
		{
			public int Id;
			public string? CardId;
			public string? Name;
			public KeyValuePair<int, int>[] Tags = Array.Empty<KeyValuePair<int, int>>();
			public object?[] Info = Array.Empty<object?>();
		}

		private static PropertyInfo[]? _infoProps;

		private List<EntityCopy> _entities = new();
		private JObject _context = new();
		public double CaptureMs { get; private set; }
		public List<string> PlayerNames { get; } = new();

		public static EntitySnapshot Capture()
		{
			var sw = Stopwatch.StartNew();
			var snap = new EntitySnapshot();
			var game = Core.Game;
			_infoProps ??= typeof(EntityInfo).GetProperties(BindingFlags.Instance | BindingFlags.Public)
				.Where(p => p.GetIndexParameters().Length == 0 && IsPlainType(p.PropertyType))
				.ToArray();

			foreach(var e in game.Entities.Values.ToList())
			{
				var copy = new EntityCopy
				{
					Id = e.Id,
					CardId = e.CardId,
					Name = e.Name,
					Tags = e.Tags.Select(t => new KeyValuePair<int, int>((int)t.Key, t.Value)).ToArray(),
					Info = _infoProps.Select(p => SafeGet(p, e.Info)).ToArray(),
				};
				snap._entities.Add(copy);
				if(e.HasTag(GameTag.PLAYER_ID) && !string.IsNullOrEmpty(e.Name))
					snap.PlayerNames.Add(e.Name!);
			}

			snap._context = new JObject
			{
				["turn"] = game.GetTurnNumber(),
				["gameEntityTurn"] = game.GameEntity?.GetTag(GameTag.TURN),
				["isBattlegroundsCombatPhase"] = game.IsBattlegroundsCombatPhase,
				["gameEntityTurnAtShoppingStart"] = game.GameEntityTurnAtShoppingStart,
				["player"] = PlayerInfo(game.Player),
				["opponent"] = PlayerInfo(game.Opponent),
				["anomalyDbfId"] = Try(() => BattlegroundsUtils.GetBattlegroundsAnomalyDbfId(game.GameEntity)),
			};
			if(!string.IsNullOrEmpty(game.Player?.Name))
				snap.PlayerNames.Add(game.Player!.Name!);
			if(!string.IsNullOrEmpty(game.Opponent?.Name))
				snap.PlayerNames.Add(game.Opponent!.Name!);

			var racesSw = Stopwatch.StartNew();
			try
			{
				var races = BattlegroundsUtils.GetAvailableRaces();
				snap._context["availableRaces"] = races == null ? null : new JArray(races.Select(r => r.ToString()));
			}
			catch(Exception ex)
			{
				snap._context["availableRacesError"] = ex.GetType().Name + ": " + ex.Message;
			}
			snap._context["availableRacesMs"] = racesSw.Elapsed.TotalMilliseconds;

			snap.CaptureMs = sw.Elapsed.TotalMilliseconds;
			return snap;
		}

		private static JObject? PlayerInfo(Player? p)
		{
			if(p == null)
				return null;
			var ids = new Func<IEnumerable<Entity>, JArray>(xs => new JArray(xs.Select(x => x.Id)));
			return new JObject
			{
				["id"] = p.Id,
				["name"] = p.Name,
				["isLocalPlayer"] = p.IsLocalPlayer,
				["hero"] = p.Hero?.Id,
				["board"] = ids(p.Board),
				["hand"] = ids(p.Hand),
				["secretZone"] = ids(p.SecretZone),
				["setAside"] = ids(p.SetAside),
				["trinkets"] = ids(p.Trinkets),
				["quests"] = ids(p.Quests),
				["questRewards"] = ids(p.QuestRewards),
				["objectives"] = ids(p.Objectives),
			};
		}

		public JObject ToJson()
		{
			var tagNames = new Dictionary<int, string>();
			string TagName(int t)
			{
				if(!tagNames.TryGetValue(t, out var n))
					tagNames[t] = n = Enum.IsDefined(typeof(GameTag), t) ? ((GameTag)t).ToString() : t.ToString();
				return n;
			}

			var entities = new JArray();
			foreach(var e in _entities)
			{
				var tags = new JObject();
				foreach(var t in e.Tags)
					tags[TagName(t.Key)] = t.Value;
				var info = new JObject();
				for(var i = 0; i < _infoProps!.Length; i++)
					info[_infoProps[i].Name] = e.Info[i] == null ? JValue.CreateNull() : new JValue(e.Info[i] is Enum ? e.Info[i]!.ToString() : e.Info[i]);
				entities.Add(new JObject
				{
					["id"] = e.Id,
					["cardId"] = e.CardId,
					["name"] = e.Name,
					["tags"] = tags,
					["info"] = info,
				});
			}
			return new JObject
			{
				["context"] = _context,
				["entityCount"] = _entities.Count,
				["entities"] = entities,
			};
		}

		private static bool IsPlainType(System.Type t)
		{
			t = Nullable.GetUnderlyingType(t) ?? t;
			return t.IsPrimitive || t.IsEnum || t == typeof(string) || t == typeof(DateTime);
		}

		private static object? SafeGet(PropertyInfo p, object target)
		{
			try
			{
				return p.GetValue(target);
			}
			catch(Exception ex)
			{
				return "$error:" + (ex.InnerException ?? ex).GetType().Name;
			}
		}

		private static JToken? Try(Func<object?> f)
		{
			try
			{
				var v = f();
				return v == null ? null : JToken.FromObject(v);
			}
			catch(Exception ex)
			{
				return "$error:" + ex.GetType().Name;
			}
		}
	}
}
