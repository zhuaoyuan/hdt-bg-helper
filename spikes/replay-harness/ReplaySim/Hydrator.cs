using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json.Linq;

namespace ReplaySim
{
	/// <summary>
	/// Rebuilds a BobsBuddy Input graph from a ReflectionDumper JSON tree (fields only, with $id/$ref).
	/// </summary>
	internal sealed class Hydrator
	{
		private static readonly HashSet<string> MetaKeys = new(StringComparer.Ordinal)
		{
			"$id", "$type", "$ref", "$skipped", "$error", "$truncated", "$entity", "$card", "$dbCard", "$itemsTruncated",
		};

		private static readonly HashSet<string> SkipFieldNames = new(StringComparer.Ordinal)
		{
			"Simulator", "FriendlySide", "OpposingSide", "TeammateSide", "FriendlyHand",
		};

		private static readonly string[] PlayerSideProps = { "Player", "Opponent", "PlayerTeammate", "OpponentTeammate" };

		private readonly Assembly _bb;
		private readonly object _simulator;
		private readonly Dictionary<int, object> _byId = new();
		private readonly Dictionary<Type, FieldInfo[]> _fieldCache = new();
		private readonly List<string> _warnings = new();

		public IReadOnlyList<string> Warnings => _warnings;

		public Hydrator(Assembly bobsBuddy, object simulator)
		{
			_bb = bobsBuddy;
			_simulator = simulator;
		}

		public object HydrateInput(JToken root)
		{
			if(root is not JObject obj)
				throw new ArgumentException("Input root must be a JSON object");

			var inputType = _bb.GetType("BobsBuddy.Simulation.Input", true);
			var input = Activator.CreateInstance(inputType);
			RegisterId(obj, input);

			// Bind dumped Player/Opponent ids to the instances Input already owns.
			foreach(var name in PlayerSideProps)
			{
				if(obj[name] is not JObject sideObj)
					continue;
				var existing = GetProp(input, name) ?? GetFieldValue(input, name);
				if(existing == null)
					continue;
				RegisterId(sideObj, existing);
				// Player._input often $ref-cycles back to Input
				SetMember(existing, "_input", input);
			}

			FillObject(input, obj);
			WireBoardReferences(input);
			return input;
		}

		public void ApplyPerturbation(object input, string path, string value)
		{
			// Path like Player.DeepBluesCounter or Opponent.AnySpellCounter
			var parts = path.Split('.');
			object cur = input;
			for(var i = 0; i < parts.Length - 1; i++)
			{
				cur = GetProp(cur, parts[i]) ?? GetFieldValue(cur, parts[i])
					?? throw new ArgumentException("Perturb path not found: " + path);
			}
			var leaf = parts[parts.Length - 1];
			var field = FindField(cur.GetType(), leaf);
			var prop = cur.GetType().GetProperty(leaf, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
			if(field != null)
				field.SetValue(cur, ConvertTo(value, field.FieldType));
			else if(prop != null && prop.CanWrite)
				prop.SetValue(cur, ConvertTo(value, prop.PropertyType));
			else
				throw new ArgumentException("Perturb leaf not writable: " + path);
		}

		private void FillObject(object target, JObject obj)
		{
			foreach(var prop in obj.Properties())
			{
				if(MetaKeys.Contains(prop.Name) || SkipFieldNames.Contains(prop.Name))
					continue;
				if(prop.Name == "_input" && target.GetType().Name == "Player")
					continue;

				// Input.Player / Opponent already registered; just fill.
				if(PlayerSideProps.Contains(prop.Name) && prop.Value is JObject sideObj)
				{
					var existing = GetProp(target, prop.Name) ?? GetFieldValue(target, prop.Name);
					if(existing != null)
					{
						FillObject(existing, sideObj);
						continue;
					}
				}

				if(!TryGetWritable(target, prop.Name, out var memberType, out var setter))
				{
					_warnings.Add("no member: " + target.GetType().Name + "." + prop.Name);
					continue;
				}

				try
				{
					var value = Materialize(prop.Value, memberType, parent: target, memberName: prop.Name);
					setter(value);
				}
				catch(Exception ex)
				{
					_warnings.Add(target.GetType().Name + "." + prop.Name + ": " + ex.GetType().Name + ": " + ex.Message);
				}
			}
		}

		private object Materialize(JToken token, Type expectedType, object parent, string memberName)
		{
			if(token == null || token.Type == JTokenType.Null)
				return null;

			if(token is JObject jobj)
			{
				if(jobj["$ref"] != null && jobj["$type"] == null)
				{
					var id = jobj["$ref"]!.Value<int>();
					if(_byId.TryGetValue(id, out var existing))
						return existing;
					_warnings.Add("unresolved $ref " + id + " for " + memberName);
					return null;
				}
				if(jobj["$skipped"] != null || jobj["$error"] != null || jobj["$truncated"] != null)
					return null;
				if(jobj["$entity"] != null || jobj["$card"] != null || jobj["$dbCard"] != null)
					return null;

				if(jobj["items"] is JArray || jobj["entries"] is JArray)
					return MaterializeCollection(jobj, expectedType, parent, memberName);

				return MaterializeObject(jobj, expectedType, parent, memberName);
			}

			if(token is JArray arr)
			{
				// rare: bare array
				var listType = expectedType;
				if(listType != null && listType.IsArray)
				{
					var elem = listType.GetElementType();
					var list = new ArrayList();
					foreach(var item in arr)
						list.Add(Materialize(item, elem, parent, memberName));
					var a = Array.CreateInstance(elem, list.Count);
					list.CopyTo(a);
					return a;
				}
			}

			return ConvertToken(token, expectedType);
		}

		private object MaterializeCollection(JObject jobj, Type expectedType, object parent, string memberName)
		{
			if(jobj["entries"] is JArray entries)
			{
				var dict = CreateDictionary(expectedType);
				var keyType = typeof(object);
				var valType = typeof(object);
				if(expectedType != null && expectedType.IsGenericType)
				{
					var args = expectedType.GetGenericArguments();
					if(args.Length >= 2)
					{
						keyType = args[0];
						valType = args[1];
					}
				}
				foreach(var entry in entries.OfType<JArray>())
				{
					if(entry.Count < 2) continue;
					var k = Materialize(entry[0], keyType, parent, memberName);
					var v = Materialize(entry[1], valType, parent, memberName);
					dict[k!] = v;
				}
				RegisterId(jobj, dict);
				return dict;
			}

			var items = (JArray)jobj["items"]!;
			var elemType = GetElementType(expectedType) ?? InferElementType(items);

			// Prefer clearing / filling an existing list on the parent (Side, Hand, …).
			var existing = parent != null ? (GetProp(parent, memberName) ?? GetFieldValue(parent, memberName)) : null;
			if(existing is IList list && !list.IsFixedSize)
			{
				list.Clear();
				RegisterId(jobj, list);
				foreach(var item in items)
				{
					var el = Materialize(item, elemType, parent, memberName);
					if(el != null)
						list.Add(el);
				}
				return list;
			}

			var created = CreateList(expectedType, elemType);
			RegisterId(jobj, created);
			foreach(var item in items)
			{
				var el = Materialize(item, elemType, parent, memberName);
				if(el != null)
					created.Add(el);
			}

			if(expectedType != null && expectedType.IsArray)
			{
				var a = Array.CreateInstance(elemType ?? typeof(object), created.Count);
				created.CopyTo(a, 0);
				return a;
			}
			return created;
		}

		private object MaterializeObject(JObject jobj, Type expectedType, object parent, string memberName)
		{
			var typeName = jobj["$type"]?.Value<string>();
			var type = ResolveType(typeName) ?? expectedType;
			if(type == null)
			{
				_warnings.Add("unknown type " + typeName + " for " + memberName);
				return null;
			}

			if(_byId.TryGetValue(jobj["$id"]?.Value<int>() ?? -1, out var already) && jobj["$id"] != null)
			{
				FillObject(already, jobj);
				return already;
			}

			object instance;
			if(IsMinionType(type))
				instance = CreateMinion(jobj, type);
			else if(IsTrinketType(type))
				instance = CreateFromFactory("TrinketFactory", "CreateFromCardId", jobj, type) ?? CreateWithConstructor(type, jobj);
			else if(type.Name.Contains("Objective") && HasFactory("ObjectiveFactory"))
				instance = CreateFromFactory("ObjectiveFactory", "CreateFromCardId", jobj, type) ?? CreateWithConstructor(type, jobj);
			else if(type.Name.Contains("Anomaly") || typeName == "BobsBuddy.Anomaly")
				instance = CreateFromFactory("AnomalyFactory", "CreateFromCardId", jobj, type) ?? CreateWithConstructor(type, jobj);
			else
				instance = CreateWithConstructor(type, jobj);

			if(instance == null)
				return null;

			RegisterId(jobj, instance);
			FillObject(instance, jobj);
			return instance;
		}

		private object CreateMinion(JObject jobj, Type type)
		{
			var cardId = jobj["CardID"]?.Value<string>() ?? jobj["CardId"]?.Value<string>();
			var controlled = jobj["ControlledByPlayer"]?.Value<bool>() ?? true;
			if(!string.IsNullOrEmpty(cardId))
			{
				var factory = GetFactory("MinionFactory");
				var create = factory.GetType().GetMethod("CreateFromCardId", new[] { typeof(string), typeof(bool) });
				if(create != null)
				{
					var m = create.Invoke(factory, new object[] { cardId, controlled });
					if(m != null)
						return m;
				}
			}
			return CreateWithConstructor(type, jobj);
		}

		private object CreateFromFactory(string factoryField, string method, JObject jobj, Type type)
		{
			var cardId = jobj["CardID"]?.Value<string>() ?? jobj["CardId"]?.Value<string>() ?? jobj["Id"]?.Value<string>();
			if(string.IsNullOrEmpty(cardId) || !HasFactory(factoryField))
				return null;
			var factory = GetFactory(factoryField);
			var create = factory.GetType().GetMethod(method, new[] { typeof(string), typeof(bool) })
				?? factory.GetType().GetMethod(method, new[] { typeof(string) });
			if(create == null)
				return null;
			var controlled = jobj["ControlledByPlayer"]?.Value<bool>() ?? true;
			var args = create.GetParameters().Length == 2
				? new object[] { cardId, controlled }
				: new object[] { cardId };
			return create.Invoke(factory, args);
		}

		private object CreateWithConstructor(Type type, JObject jobj)
		{
			// Prefer (string cardId, bool controlledByPlayer, Simulator)
			var cardId = jobj["CardID"]?.Value<string>() ?? jobj["CardId"]?.Value<string>() ?? jobj["Id"]?.Value<string>() ?? "";
			var controlled = jobj["ControlledByPlayer"]?.Value<bool>() ?? true;
			var simType = _simulator.GetType();

			foreach(var ctor in type.GetConstructors(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
			{
				var ps = ctor.GetParameters();
				try
				{
					if(ps.Length == 0)
						return ctor.Invoke(null);
					if(ps.Length == 1 && ps[0].ParameterType.IsAssignableFrom(simType))
						return ctor.Invoke(new[] { _simulator });
					if(ps.Length == 1 && ps[0].ParameterType.Name == "Input")
						return null; // Player(Input) — should use existing
					if(ps.Length == 2 && ps[0].ParameterType == typeof(string) && ps[1].ParameterType == typeof(bool))
						return ctor.Invoke(new object[] { cardId, controlled });
					if(ps.Length == 3 && ps[0].ParameterType == typeof(string) && ps[1].ParameterType == typeof(bool)
						&& ps[2].ParameterType.IsAssignableFrom(simType))
						return ctor.Invoke(new object[] { cardId, controlled, _simulator });
					if(ps.Length == 2 && ps[0].ParameterType.Name.Contains("Minion") && ps[1].ParameterType.IsAssignableFrom(simType))
					{
						// MinionCardEntity(Minion, ?, Simulator) — need nested minion first; fall through
					}
					if(ps.Length == 3 && ps[2].ParameterType.IsAssignableFrom(simType))
					{
						// CardEntity variants: (Minion minion, Entity? unused, Simulator)
						object arg0 = null;
						if(jobj["_minion"] is JObject minObj || jobj["minion"] is JObject)
						{
							var mo = (JObject)(jobj["_minion"] ?? jobj["minion"]);
							arg0 = MaterializeObject(mo, null, null, "minion");
						}
						else if(!string.IsNullOrEmpty(cardId) && IsMinionType(ps[0].ParameterType))
							arg0 = CreateMinion(jobj, ps[0].ParameterType);
						return ctor.Invoke(new[] { arg0, null, _simulator });
					}
				}
				catch(Exception ex)
				{
					_warnings.Add("ctor " + type.Name + ": " + ex.GetType().Name + ": " + (ex.InnerException?.Message ?? ex.Message));
				}
			}

			if(type.ContainsGenericParameters)
			{
				_warnings.Add("skip open generic " + type);
				return null;
			}

			// Last resort: uninitialized then fields
			try
			{
				return System.Runtime.Serialization.FormatterServices.GetUninitializedObject(type);
			}
			catch(Exception ex)
			{
				_warnings.Add("create failed " + type.Name + ": " + ex.Message);
				return null;
			}
		}

		private void WireBoardReferences(object input)
		{
			var player = GetProp(input, "Player");
			var opponent = GetProp(input, "Opponent");
			var playerSide = GetProp(player, "Side") as IList;
			var oppSide = GetProp(opponent, "Side") as IList;
			var playerHand = GetProp(player, "Hand") as IList;
			var oppHand = GetProp(opponent, "Hand") as IList;

			void WireOwner(object owner, IList friendlySide, IList opposingSide, IList friendlyHand)
			{
				if(owner == null) return;
				foreach(var collName in new[] { "Side", "Hand", "HeroPowers", "Trinkets", "Quests", "Objectives", "Secrets" })
				{
					if(GetProp(owner, collName) is not IList coll) continue;
					foreach(var item in coll)
						WireEntity(item, friendlySide, opposingSide, friendlyHand);
				}
			}

			WireOwner(player, playerSide, oppSide, playerHand);
			WireOwner(opponent, oppSide, playerSide, oppHand);
		}

		private void WireEntity(object entity, IList friendlySide, IList opposingSide, IList friendlyHand)
		{
			if(entity == null) return;
			SetMember(entity, "Simulator", _simulator);
			SetMember(entity, "FriendlySide", friendlySide);
			SetMember(entity, "OpposingSide", opposingSide);
			SetMember(entity, "FriendlyHand", friendlyHand);

			var enchants = GetFieldValue(entity, "_enchantments") as IList ?? GetProp(entity, "Enchantments") as IList;
			if(enchants != null)
			{
				foreach(var e in enchants)
				{
					if(e == null) continue;
					SetMember(e, "Simulator", _simulator);
					SetMember(e, "FriendlySide", friendlySide);
					SetMember(e, "OpposingSide", opposingSide);
					SetMember(e, "FriendlyHand", friendlyHand);
					SetMember(e, "AttachedTo", entity);
				}
			}

			var attached = GetProp(entity, "AttachedMinion") ?? GetFieldValue(entity, "AttachedMinion");
			if(attached != null)
				WireEntity(attached, friendlySide, opposingSide, friendlyHand);
		}

		private void RegisterId(JObject obj, object instance)
		{
			if(obj["$id"] == null || instance == null) return;
			_byId[obj["$id"].Value<int>()] = instance;
		}

		private Type ResolveType(string typeName)
		{
			if(string.IsNullOrEmpty(typeName)) return null;
			// Dumper writes List<T> / ValueTuple<T> style names; close them when we can.
			if(typeName.Contains("<"))
			{
				var tick = typeName.IndexOf('<');
				var close = typeName.LastIndexOf('>');
				var open = typeName.Substring(0, tick);
				var inner = close > tick ? typeName.Substring(tick + 1, close - tick - 1) : "";
				var args = SplitTypeArgs(inner).Select(ResolveType).ToArray();
				if(args.Length > 0 && args.All(a => a != null))
				{
					var def = _bb.GetType(open + "`" + args.Length)
						?? Type.GetType(open + "`" + args.Length)
						?? AppDomain.CurrentDomain.GetAssemblies()
							.Select(a => a.GetType(open + "`" + args.Length)).FirstOrDefault(t => t != null);
					if(def != null)
						return def.MakeGenericType(args);
				}
				return null; // do not return open generics
			}
			return _bb.GetType(typeName)
				?? Type.GetType(typeName)
				?? AppDomain.CurrentDomain.GetAssemblies().Select(a => a.GetType(typeName)).FirstOrDefault(t => t != null);
		}

		private static List<string> SplitTypeArgs(string inner)
		{
			var parts = new List<string>();
			if(string.IsNullOrEmpty(inner)) return parts;
			var depth = 0;
			var start = 0;
			for(var i = 0; i < inner.Length; i++)
			{
				var c = inner[i];
				if(c == '<') depth++;
				else if(c == '>') depth--;
				else if(c == ',' && depth == 0)
				{
					parts.Add(inner.Substring(start, i - start).Trim());
					start = i + 1;
				}
			}
			parts.Add(inner.Substring(start).Trim());
			return parts;
		}

		private bool IsMinionType(Type type) =>
			type != null && (type.Name == "Minion" || typeof(object).Assembly != type.Assembly
				&& (type.FullName?.StartsWith("BobsBuddy.Minion", StringComparison.Ordinal) == true
					|| type.FullName?.StartsWith("BobsBuddy.Minions.", StringComparison.Ordinal) == true
					|| InheritsName(type, "Minion")));

		private bool IsTrinketType(Type type) =>
			type != null && (type.Name == "Trinket" || InheritsName(type, "Trinket")
				|| type.FullName?.StartsWith("BobsBuddy.Trinkets.", StringComparison.Ordinal) == true);

		private static bool InheritsName(Type type, string name)
		{
			for(var t = type; t != null; t = t.BaseType)
				if(t.Name == name) return true;
			return false;
		}

		private bool HasFactory(string name) =>
			_simulator.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic) != null;

		private object GetFactory(string name)
		{
			var f = _simulator.GetType().GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)
				?? throw new MissingFieldException("Simulator." + name);
			return f.GetValue(_simulator);
		}

		private bool TryGetWritable(object target, string name, out Type memberType, out Action<object> setter)
		{
			memberType = null;
			setter = null;
			var field = FindField(target.GetType(), name);
			if(field != null)
			{
				memberType = field.FieldType;
				setter = v => field.SetValue(target, v);
				return true;
			}
			var prop = target.GetType().GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
			if(prop != null && prop.CanWrite)
			{
				memberType = prop.PropertyType;
				setter = v => prop.SetValue(target, v);
				return true;
			}
			// read-only list property: still allow filling via getter
			if(prop != null && typeof(IList).IsAssignableFrom(prop.PropertyType))
			{
				memberType = prop.PropertyType;
				setter = v => { /* filled in MaterializeCollection via parent getter */ };
				return true;
			}
			return false;
		}

		private FieldInfo FindField(Type type, string name)
		{
			foreach(var f in GetFields(type))
			{
				var n = f.Name;
				if(n.StartsWith("<", StringComparison.Ordinal) && n.IndexOf('>') is var end and > 1)
					n = n.Substring(1, end - 1);
				if(n == name || f.Name == name)
					return f;
			}
			return null;
		}

		private FieldInfo[] GetFields(Type type)
		{
			if(_fieldCache.TryGetValue(type, out var cached))
				return cached;
			var fields = new List<FieldInfo>();
			for(var t = type; t != null && t != typeof(object); t = t.BaseType)
				fields.AddRange(t.GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly));
			return _fieldCache[type] = fields.ToArray();
		}

		private static object GetProp(object obj, string name)
		{
			if(obj == null) return null;
			return obj.GetType().GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic)?.GetValue(obj);
		}

		private object GetFieldValue(object obj, string name)
		{
			if(obj == null) return null;
			return FindField(obj.GetType(), name)?.GetValue(obj);
		}

		private void SetMember(object obj, string name, object value)
		{
			if(obj == null) return;
			var field = FindField(obj.GetType(), name);
			if(field != null)
			{
				try { field.SetValue(obj, Coerce(value, field.FieldType)); }
				catch { /* ignore wire failures */ }
				return;
			}
			var prop = obj.GetType().GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic);
			if(prop != null && prop.CanWrite)
			{
				try { prop.SetValue(obj, Coerce(value, prop.PropertyType)); }
				catch { /* ignore */ }
			}
		}

		private static object Coerce(object value, Type target)
		{
			if(value == null) return null;
			if(target.IsInstanceOfType(value)) return value;
			return value;
		}

		private static Type GetElementType(Type collectionType)
		{
			if(collectionType == null) return null;
			if(collectionType.IsArray) return collectionType.GetElementType();
			if(collectionType.IsGenericType)
			{
				var args = collectionType.GetGenericArguments();
				if(args.Length == 1) return args[0];
			}
			foreach(var i in collectionType.GetInterfaces())
			{
				if(i.IsGenericType && i.GetGenericTypeDefinition() == typeof(IEnumerable<>))
					return i.GetGenericArguments()[0];
			}
			return null;
		}

		private Type InferElementType(JArray items)
		{
			foreach(var item in items.OfType<JObject>())
			{
				var t = ResolveType(item["$type"]?.Value<string>());
				if(t != null) return t;
			}
			return typeof(object);
		}

		private static IList CreateList(Type expectedType, Type elemType)
		{
			elemType ??= typeof(object);
			if(expectedType != null && !expectedType.IsInterface && !expectedType.IsAbstract && typeof(IList).IsAssignableFrom(expectedType)
				&& expectedType.GetConstructor(Type.EmptyTypes) != null)
				return (IList)Activator.CreateInstance(expectedType);

			var listType = typeof(List<>).MakeGenericType(elemType);
			return (IList)Activator.CreateInstance(listType);
		}

		private static IDictionary CreateDictionary(Type expectedType)
		{
			if(expectedType != null && !expectedType.IsInterface && typeof(IDictionary).IsAssignableFrom(expectedType)
				&& expectedType.GetConstructor(Type.EmptyTypes) != null)
				return (IDictionary)Activator.CreateInstance(expectedType);
			if(expectedType != null && expectedType.IsGenericType)
			{
				var args = expectedType.GetGenericArguments();
				if(args.Length == 2)
					return (IDictionary)Activator.CreateInstance(typeof(Dictionary<,>).MakeGenericType(args));
			}
			return new Hashtable();
		}

		private object ConvertToken(JToken token, Type expectedType)
		{
			if(expectedType == null)
				return ((JValue)token).Value;

			if(expectedType.IsEnum)
			{
				var s = token.Type == JTokenType.String ? token.Value<string>() : token.ToString();
				return Enum.Parse(expectedType, s, ignoreCase: true);
			}

			var underlying = Nullable.GetUnderlyingType(expectedType) ?? expectedType;
			if(token.Type == JTokenType.Null)
				return null;

			if(underlying == typeof(Guid))
				return Guid.Parse(token.Value<string>());

			try
			{
				return token.ToObject(underlying);
			}
			catch
			{
				return Convert.ChangeType(((JValue)token).Value, underlying, CultureInfo.InvariantCulture);
			}
		}

		private static object ConvertTo(string value, Type target)
		{
			var underlying = Nullable.GetUnderlyingType(target) ?? target;
			if(underlying.IsEnum)
				return Enum.Parse(underlying, value, true);
			if(underlying == typeof(bool))
				return bool.Parse(value);
			if(underlying == typeof(int))
				return int.Parse(value, CultureInfo.InvariantCulture);
			if(underlying == typeof(double))
				return double.Parse(value, CultureInfo.InvariantCulture);
			if(underlying == typeof(float))
				return float.Parse(value, CultureInfo.InvariantCulture);
			if(underlying == typeof(string))
				return value;
			return Convert.ChangeType(value, underlying, CultureInfo.InvariantCulture);
		}
	}
}
