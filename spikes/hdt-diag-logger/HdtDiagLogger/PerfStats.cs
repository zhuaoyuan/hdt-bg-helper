using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Threading;
using Newtonsoft.Json.Linq;

namespace HdtDiagLogger
{
	/// <summary>Per-category call-duration histograms, plus the managed thread ids each category ran on.</summary>
	internal sealed class PerfStats
	{
		// upper bounds in microseconds; the last bucket is open-ended
		private static readonly long[] BoundsUs = { 10, 30, 100, 300, 1_000, 3_000, 10_000, 30_000, 100_000, 300_000 };

		private sealed class Category
		{
			public readonly long[] Buckets = new long[BoundsUs.Length + 1];
			public long Count;
			public double TotalMs;
			public double MaxMs;
			public readonly HashSet<int> Threads = new();
		}

		private readonly Dictionary<string, Category> _categories = new();

		public void Add(string name, Stopwatch sw) => Add(name, sw.Elapsed.TotalMilliseconds);

		public void Add(string name, double ms)
		{
			if(!_categories.TryGetValue(name, out var c))
				_categories[name] = c = new Category();
			var us = (long)(ms * 1000);
			var i = 0;
			while(i < BoundsUs.Length && us >= BoundsUs[i])
				i++;
			c.Buckets[i]++;
			c.Count++;
			c.TotalMs += ms;
			if(ms > c.MaxMs)
				c.MaxMs = ms;
			c.Threads.Add(Thread.CurrentThread.ManagedThreadId);
		}

		public JObject ToJson() => new(_categories.Select(kv => new JProperty(kv.Key, new JObject
		{
			["count"] = kv.Value.Count,
			["totalMs"] = kv.Value.TotalMs,
			["maxMs"] = kv.Value.MaxMs,
			["p50UpperUs"] = Percentile(kv.Value, 0.50),
			["p99UpperUs"] = Percentile(kv.Value, 0.99),
			["bucketUpperUs"] = new JArray(BoundsUs.Cast<object>().Append("inf")),
			["buckets"] = new JArray(kv.Value.Buckets),
			["threads"] = new JArray(kv.Value.Threads),
		})));

		private static JToken Percentile(Category c, double q)
		{
			long seen = 0;
			for(var i = 0; i < c.Buckets.Length; i++)
			{
				seen += c.Buckets[i];
				if(seen >= q * c.Count)
					return i < BoundsUs.Length ? BoundsUs[i] : "inf";
			}
			return "inf";
		}
	}
}
