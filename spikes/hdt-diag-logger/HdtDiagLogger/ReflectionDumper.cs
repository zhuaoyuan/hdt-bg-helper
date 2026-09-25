using System;
using System.Collections;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Hearthstone_Deck_Tracker.Hearthstone;
using Hearthstone_Deck_Tracker.Hearthstone.Entities;
using Newtonsoft.Json.Linq;

namespace HdtDiagLogger
{
	/// <summary>
	/// Converts an arbitrary object graph into a JSON tree by reading fields only (never property getters, which may
	/// have side effects). Repeated references become {"$ref": id}; depth, node count and collection size are capped.
	/// </summary>
	internal sealed class ReflectionDumper
	{
		private const BindingFlags InstanceFields = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.DeclaredOnly;

		private static readonly Dictionary<Type, FieldInfo[]> FieldCache = new();

		private static readonly string[] SkippedTypePrefixes =
		{
			"System.Threading.", "System.Reflection.", "System.Runtime.", "System.Windows.", "System.IO.",
			"Hearthstone_Deck_Tracker.Hearthstone.GameV2", "Hearthstone_Deck_Tracker.Hearthstone.Player",
			"BobsBuddy.Simulation.Simulator",
		};

		public int MaxDepth { get; set; } = 24;
		public int MaxNodes { get; set; } = 200_000;
		// Output.damageResults holds one entry per simulation (up to 10,000)
		public int MaxItems { get; set; } = 20_000;

		private readonly Dictionary<object, int> _ids = new(ReferenceComparer.Instance);
		private int _nodes;

		public bool Truncated { get; private set; }
		public int Nodes => _nodes;

		public JToken Dump(object? value) => Dump(value, 0);

		private JToken Dump(object? value, int depth)
		{
			if(value == null)
				return JValue.CreateNull();
			var type = value.GetType();

			if(type.IsEnum || value is IntPtr || value is UIntPtr)
				return new JValue(value.ToString());
			if(type.IsPrimitive || value is string || value is decimal || value is DateTime || value is Guid || value is TimeSpan)
				return new JValue(value);

			if(value is Entity entity)
				return new JObject { ["$entity"] = entity.Id, ["cardId"] = entity.CardId };
			if(value is Card card)
				return new JObject { ["$card"] = card.Id };
			if(value is HearthDb.Card dbCard)
				return new JObject { ["$dbCard"] = dbCard.Id };
			if(value is Delegate || value is Task || value is Type || value is MemberInfo || IsSkipped(type))
				return new JObject { ["$skipped"] = type.FullName };

			if(++_nodes > MaxNodes || depth > MaxDepth)
			{
				Truncated = true;
				return new JObject { ["$truncated"] = type.FullName };
			}

			JObject obj;
			if(!type.IsValueType)
			{
				if(_ids.TryGetValue(value, out var existing))
					return new JObject { ["$ref"] = existing };
				var id = _ids.Count + 1;
				_ids[value] = id;
				obj = new JObject { ["$id"] = id, ["$type"] = TypeName(type) };
			}
			else
				obj = new JObject { ["$type"] = TypeName(type) };

			switch(value)
			{
				case IDictionary dict:
					obj["entries"] = DumpItems(dict.Cast<DictionaryEntry>(), dict.Count,
						e => new JArray(Dump(e.Key, depth + 1), Dump(e.Value, depth + 1)), obj);
					return obj;
				case Array arr:
					obj["items"] = DumpItems(arr.Cast<object?>(), arr.Length, x => Dump(x, depth + 1), obj);
					return obj;
				case ICollection coll:
					obj["items"] = DumpItems(coll.Cast<object?>(), coll.Count, x => Dump(x, depth + 1), obj);
					return obj;
				case IEnumerable when IsGenericCollection(type):
					obj["items"] = DumpItems(((IEnumerable)value).Cast<object?>(), -1, x => Dump(x, depth + 1), obj);
					return obj;
			}

			foreach(var field in GetFields(type))
			{
				object? fieldValue;
				try
				{
					fieldValue = field.GetValue(value);
				}
				catch(Exception ex)
				{
					obj[FieldName(field, obj)] = new JObject { ["$error"] = ex.GetType().Name };
					continue;
				}
				obj[FieldName(field, obj)] = Dump(fieldValue, depth + 1);
			}
			return obj;
		}

		private JArray DumpItems<T>(IEnumerable<T> items, int count, Func<T, JToken> dump, JObject owner)
		{
			var arr = new JArray();
			try
			{
				foreach(var item in items)
				{
					if(arr.Count >= MaxItems)
					{
						owner["$itemsTruncated"] = count;
						Truncated = true;
						break;
					}
					arr.Add(dump(item));
				}
			}
			catch(InvalidOperationException ex)
			{
				// Bob's Buddy worker threads may be using the same collections
				owner["$error"] = ex.GetType().Name + ": " + ex.Message;
			}
			return arr;
		}

		// HashSet<T> etc. are finite collections that do not implement the non-generic ICollection.
		private static bool IsGenericCollection(Type type) => type.GetInterfaces()
			.Any(i => i.IsGenericType && i.GetGenericTypeDefinition() == typeof(ICollection<>));

		private static bool IsSkipped(Type type)
		{
			var name = type.FullName ?? "";
			return SkippedTypePrefixes.Any(p => name.StartsWith(p, StringComparison.Ordinal));
		}

		private static FieldInfo[] GetFields(Type type)
		{
			lock(FieldCache)
			{
				if(FieldCache.TryGetValue(type, out var cached))
					return cached;
				var fields = new List<FieldInfo>();
				for(var t = type; t != null && t != typeof(object); t = t.BaseType)
					fields.AddRange(t.GetFields(InstanceFields));
				return FieldCache[type] = fields.ToArray();
			}
		}

		private static string FieldName(FieldInfo field, JObject owner)
		{
			var name = field.Name;
			// auto-property backing field: <Name>k__BackingField
			if(name.StartsWith("<") && name.IndexOf('>') is var end and > 1)
				name = name.Substring(1, end - 1);
			// a base class may declare a private field with the same name
			return owner.ContainsKey(name) ? $"{field.DeclaringType?.Name}.{name}" : name;
		}

		private static string TypeName(Type type) => type.IsGenericType
			? $"{type.Namespace}.{type.Name.Split('`')[0]}<{string.Join(",", type.GetGenericArguments().Select(TypeName))}>"
			: type.FullName ?? type.Name;

		private sealed class ReferenceComparer : IEqualityComparer<object>
		{
			public static readonly ReferenceComparer Instance = new();
			public new bool Equals(object x, object y) => ReferenceEquals(x, y);
			public int GetHashCode(object obj) => RuntimeHelpers.GetHashCode(obj);
		}
	}
}
