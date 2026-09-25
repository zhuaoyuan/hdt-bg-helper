using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Text;
using System.Threading;

namespace HdtDiagLogger
{
	/// <summary>
	/// Owns the files of one game directory. Callers only enqueue; formatting, anonymisation and IO run on a
	/// dedicated background thread so HDT's (UI) thread is never blocked on disk.
	/// </summary>
	internal sealed class RecordWriter : IDisposable
	{
		private abstract class Item { }
		private sealed class RawItem : Item { public long Seq; public long Ms; public string Line = ""; }
		private sealed class RecordItem : Item { public Func<string> Build = () => ""; }
		private sealed class FileItem : Item { public string Name = ""; public Func<string> Build = () => ""; }

		private static readonly UTF8Encoding Utf8 = new(false);

		private readonly BlockingCollection<Item> _queue = new(new ConcurrentQueue<Item>());
		private readonly Thread _thread;
		private readonly string _dir;
		private readonly Anonymizer _anonymizer;
		private readonly StreamWriter _raw;
		private readonly StreamWriter _records;
		private readonly Action<Exception> _onError;

		public int QueueLength => _queue.Count;
		public long BytesWritten { get; private set; }

		public RecordWriter(string dir, Anonymizer anonymizer, Action<Exception> onError)
		{
			_dir = dir;
			_anonymizer = anonymizer;
			_onError = onError;
			Directory.CreateDirectory(dir);
			_raw = new StreamWriter(Path.Combine(dir, "power.log"), false, Utf8, 1 << 16);
			_records = new StreamWriter(Path.Combine(dir, "records.jsonl"), false, Utf8, 1 << 16);
			_thread = new Thread(Run) { IsBackground = true, Name = "HdtDiagLogger.Writer", Priority = ThreadPriority.BelowNormal };
			_thread.Start();
		}

		public void Raw(long seq, long ms, string line) => Add(new RawItem { Seq = seq, Ms = ms, Line = line });

		/// <summary><paramref name="build"/> runs on the writer thread and must only touch data it owns.</summary>
		public void Record(Func<string> build) => Add(new RecordItem { Build = build });

		public void File(string name, Func<string> build) => Add(new FileItem { Name = name, Build = build });

		private void Add(Item item)
		{
			try
			{
				_queue.Add(item);
			}
			catch(InvalidOperationException)
			{
				// closed concurrently; late items of a finished game are dropped
			}
		}

		private void Run()
		{
			var lastFlush = Stopwatch.StartNew();
			while(!_queue.IsCompleted)
			{
				if(!_queue.TryTake(out var item, 1000))
					item = null;
				try
				{
					switch(item)
					{
						case RawItem r:
							Write(_raw, $"{r.Seq}\t{r.Ms}\t{_anonymizer.Apply(r.Line)}");
							break;
						case RecordItem rec:
							Write(_records, _anonymizer.Apply(rec.Build()));
							break;
						case FileItem f:
							var text = _anonymizer.Apply(f.Build());
							System.IO.File.WriteAllText(Path.Combine(_dir, f.Name), text, Utf8);
							BytesWritten += text.Length;
							break;
					}
					if(lastFlush.ElapsedMilliseconds > 1000)
					{
						_raw.Flush();
						_records.Flush();
						lastFlush.Restart();
					}
				}
				catch(Exception ex)
				{
					_onError(ex);
				}
			}
			Finish();
		}

		private void Finish()
		{
			try
			{
				_raw.Dispose();
				_records.Dispose();
				var src = Path.Combine(_dir, "power.log");
				using(var input = System.IO.File.OpenRead(src))
				using(var output = System.IO.File.Create(src + ".gz"))
				using(var gz = new GZipStream(output, CompressionLevel.Optimal))
					input.CopyTo(gz);
				System.IO.File.Delete(src);
			}
			catch(Exception ex)
			{
				_onError(ex);
			}
		}

		private void Write(StreamWriter w, string line)
		{
			w.Write(line);
			w.Write('\n');
			BytesWritten += line.Length + 1;
		}

		public void Dispose() => Close(0);

		/// <summary>
		/// Stops accepting items; the writer thread drains the queue, closes the files and gzips power.log.
		/// Waits at most <paramref name="waitMs"/>; if HDT exits first, power.log stays uncompressed.
		/// </summary>
		public void Close(int waitMs)
		{
			if(_queue.IsAddingCompleted)
				return;
			_queue.CompleteAdding();
			if(waitMs > 0)
				_thread.Join(waitMs);
		}
	}
}
