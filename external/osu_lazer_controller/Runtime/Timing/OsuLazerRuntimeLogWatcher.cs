using System.Globalization;
using System.Text.RegularExpressions;

namespace OsuLazerController.Runtime.Timing;

public sealed class OsuLazerRuntimeLogWatcher
{
    private static readonly Regex SeekRegex = new(
        @"GameplayClockContainer seeking to (?<time>-?\d+(?:[\.,]\d+)?)",
        RegexOptions.Compiled);

    private readonly List<string> _logsDirs;
    private string? _logPath;
    private long _offset;
    private double _lastSeekTimeMs;

    public OsuLazerRuntimeLogWatcher(IEnumerable<string>? extraLogsDirs = null)
    {
        _logsDirs = [];
        var defaultLogsDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "osu",
            "logs");

        if (Directory.Exists(defaultLogsDir))
        {
            _logsDirs.Add(defaultLogsDir);
        }

        foreach (var dir in extraLogsDirs ?? [])
        {
            if (Directory.Exists(dir)
                && !_logsDirs.Contains(dir, StringComparer.OrdinalIgnoreCase))
            {
                _logsDirs.Add(dir);
            }
        }

        if (_logsDirs.Count == 0)
        {
            throw new InvalidOperationException("osu!lazer logs directory not found.");
        }

        _logPath = FindLatestRuntimeLog();
        _offset = _logPath is null ? 0 : SafeLength(_logPath);
    }

    public async Task<GameplayClockStart> WaitForGameplayClockStartAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            foreach (var line in ReadNewLines())
            {
                if (TryParseSeek(line, out var seekTimeMs))
                {
                    _lastSeekTimeMs = seekTimeMs;
                }

                if (line.Contains(
                        "GameplayClockContainer started via call to StartGameplayClock",
                        StringComparison.OrdinalIgnoreCase))
                {
                    return new GameplayClockStart(_lastSeekTimeMs);
                }
            }

            await Task.Delay(10, cancellationToken);
        }

        return new GameplayClockStart(_lastSeekTimeMs);
    }

    public List<GameplayClockEvent> PollEvents()
    {
        var result = new List<GameplayClockEvent>();
        foreach (var line in ReadNewLines())
        {
            if (TryParseSeek(line, out var seekTimeMs))
            {
                _lastSeekTimeMs = seekTimeMs;
                result.Add(new GameplayClockEvent(GameplayClockEventKind.Seek, seekTimeMs));
                continue;
            }

            if (line.Contains(
                    "GameplayClockContainer started via call to StartGameplayClock",
                    StringComparison.OrdinalIgnoreCase))
            {
                result.Add(new GameplayClockEvent(GameplayClockEventKind.Start, _lastSeekTimeMs));
                continue;
            }

            if (line.Contains(
                    "GameplayClockContainer stopped via call to StopGameplayClock",
                    StringComparison.OrdinalIgnoreCase))
            {
                result.Add(new GameplayClockEvent(GameplayClockEventKind.Stop, _lastSeekTimeMs));
            }
        }

        return result;
    }

    private IEnumerable<string> ReadNewLines()
    {
        var latest = FindLatestRuntimeLog();
        if (latest is not null && !string.Equals(latest, _logPath, StringComparison.OrdinalIgnoreCase))
        {
            _logPath = latest;
            _offset = SafeLength(latest);
        }

        if (_logPath is null)
        {
            yield break;
        }

        string text;
        try
        {
            using var stream = new FileStream(_logPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            if (_offset > stream.Length)
            {
                _offset = 0;
            }

            stream.Seek(_offset, SeekOrigin.Begin);
            using var reader = new StreamReader(stream);
            text = reader.ReadToEnd();
            _offset = stream.Position;
        }
        catch
        {
            yield break;
        }

        foreach (var line in text.Split(Environment.NewLine, StringSplitOptions.RemoveEmptyEntries))
        {
            yield return line;
        }
    }

    private string? FindLatestRuntimeLog()
    {
        try
        {
            return _logsDirs
                .SelectMany(dir => Directory.EnumerateFiles(dir, "*.runtime.log"))
                .OrderByDescending(File.GetLastWriteTimeUtc)
                .FirstOrDefault();
        }
        catch
        {
            return null;
        }
    }

    private static bool TryParseSeek(string line, out double seekTimeMs)
    {
        seekTimeMs = 0.0;
        var match = SeekRegex.Match(line);
        if (!match.Success)
        {
            return false;
        }

        var value = match.Groups["time"].Value.Replace(',', '.');
        return double.TryParse(value, NumberStyles.Float, CultureInfo.InvariantCulture, out seekTimeMs);
    }

    private static long SafeLength(string path)
    {
        try
        {
            return new FileInfo(path).Length;
        }
        catch
        {
            return 0;
        }
    }
}

public sealed record GameplayClockStart(double SeekTimeMs);

public sealed record GameplayClockEvent(GameplayClockEventKind Kind, double SeekTimeMs);

public enum GameplayClockEventKind
{
    Seek,
    Start,
    Stop,
}
