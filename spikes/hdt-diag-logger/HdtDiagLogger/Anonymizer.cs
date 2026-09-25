using System;
using System.Collections.Concurrent;
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

		private readonly byte[] _salt;
		private readonly ConcurrentDictionary<string, string> _cache = new();
		private volatile string[] _knownNames = Array.Empty<string>();

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
			var current = _knownNames;
			if(current.Contains(name) && (bare.Length < MinNameLength || current.Contains(bare)))
				return;
			_knownNames = current.Concat(new[] { name, bare }).Where(x => x.Length >= MinNameLength).Distinct()
				.OrderByDescending(x => x.Length).ToArray();
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
			foreach(var name in _knownNames)
			{
				if(text.IndexOf(name, StringComparison.Ordinal) >= 0)
					text = text.Replace(name, Placeholder(name.Split('#')[0]));
			}
			return text;
		}
	}
}
