using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace HdtDiagLogger
{
	/// <summary>Replaces BattleTags, known player names and account ids with salted-hash placeholders.</summary>
	internal sealed class Anonymizer
	{
		// Name#1234: the name part stops at whitespace and at characters that delimit values in Power.log / JSON.
		private static readonly Regex BattleTag = new(@"[^\s=#\[\]""',:{}()]{1,24}#\d{3,6}", RegexOptions.Compiled);
		private const int MinNameLength = 2;
		private static readonly Regex AccountId = new(@"(hi|lo)=\d{6,}", RegexOptions.Compiled);

		/// <summary>
		/// Bare names that are also Bob's Buddy / dump structural identifiers. Replacing them as substrings
		/// (or even as whole tokens next to <c>.</c> / JSON quotes) corrupts Input keys and <c>$type</c>.
		/// BattleTags like <c>Player#1234</c> are still anonymised via <see cref="BattleTag"/>.
		/// See facts/diag-capture-batch-20261003.md §4.1 and facts/replay-roundtrip.md.
		/// </summary>
		private static readonly HashSet<string> ReservedBareNames = new(StringComparer.Ordinal)
		{
			"Player",
			"Opponent",
			"PlayerTeammate",
			"OpponentTeammate",
			"ControlledByPlayer",
			"DuosInputPlayer",
			"DuosInputPlayerTeammate",
			"Windfury",
			"MegaWindfury",
			"Simulation",
		};

		// Identifier-ish characters for word boundaries. Include '.' so namespace segments in $type
		// (e.g. BobsBuddy.Simulation.Player) are not treated as bare name tokens.
		private const string BoundaryClass = @"A-Za-z0-9_.";

		private readonly byte[] _salt;
		private readonly ConcurrentDictionary<string, string> _cache = new();
		private volatile NameRule[] _rules = Array.Empty<NameRule>();

		private sealed class NameRule
		{
			public string Name = "";
			public string Token = "";
			public Regex Pattern = null!;
		}

		public Anonymizer(string saltFile)
		{
			if(File.Exists(saltFile))
				_salt = Convert.FromBase64String(File.ReadAllText(saltFile).Trim());
			else
			{
				_salt = new byte[16];
				using(var rng = RandomNumberGenerator.Create())
					rng.GetBytes(_salt);
				File.WriteAllText(saltFile, Convert.ToBase64String(_salt));
			}
		}

		/// <summary>Player names that may appear without a #discriminator (e.g. entity names).</summary>
		public void AddKnownName(string? name)
		{
			// Chinese names are often two characters; shorter matches would clobber unrelated text.
			if(string.IsNullOrWhiteSpace(name) || name!.Length < MinNameLength)
				return;
			var bare = name.Split('#')[0];
			var current = _rules;
			var haveFull = current.Any(r => r.Name == name);
			var haveBare = bare.Length < MinNameLength || ReservedBareNames.Contains(bare)
				|| current.Any(r => r.Name == bare);
			if(haveFull && haveBare)
				return;

			var names = current.Select(r => r.Name).ToList();
			if(!haveFull)
				names.Add(name);
			if(!haveBare && bare.Length >= MinNameLength && !ReservedBareNames.Contains(bare))
				names.Add(bare);

			_rules = names
				.Where(x => x.Length >= MinNameLength)
				.Distinct()
				.OrderByDescending(x => x.Length)
				.Select(n => new NameRule
				{
					Name = n,
					Token = n.Split('#')[0],
					Pattern = new Regex(
						$@"(?<![{BoundaryClass}]){Regex.Escape(n)}(?![{BoundaryClass}])",
						RegexOptions.Compiled),
				})
				.ToArray();
		}

		public string Placeholder(string value) => _cache.GetOrAdd(value, v =>
		{
			using var sha = SHA256.Create();
			var hash = sha.ComputeHash(_salt.Concat(Encoding.UTF8.GetBytes(v)).ToArray());
			return "player_" + BitConverter.ToString(hash, 0, 4).Replace("-", "").ToLowerInvariant();
		});

		public string Apply(string text)
		{
			text = BattleTag.Replace(text, m => Placeholder(m.Value.Split('#')[0]));
			text = AccountId.Replace(text, m => m.Groups[1].Value + "=" + Placeholder(m.Value));
			foreach(var rule in _rules)
			{
				if(text.IndexOf(rule.Name, StringComparison.Ordinal) < 0)
					continue;
				var placeholder = Placeholder(rule.Token);
				text = rule.Pattern.Replace(text, placeholder);
			}
			return text;
		}
	}
}
