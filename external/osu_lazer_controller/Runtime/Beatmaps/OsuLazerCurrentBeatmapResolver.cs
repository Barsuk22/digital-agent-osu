using System.Text.RegularExpressions;

namespace OsuLazerController.Runtime.Beatmaps;

public sealed class OsuLazerCurrentBeatmapResolver
{
    private static readonly Regex WorkingBeatmapRegex = new(
        @"Game-wide working beatmap updated to (?<display>.+)$",
        RegexOptions.Compiled);

    private static readonly Regex DisplayRegex = new(
        @"^(?<artist>.+) - (?<title>.+) \((?<creator>.+)\) \[(?<version>[^\]]+)\]$",
        RegexOptions.Compiled);

    private readonly List<string> _extraDataRoots;

    public OsuLazerCurrentBeatmapResolver(IEnumerable<string>? extraDataRoots = null)
    {
        _extraDataRoots = (extraDataRoots ?? [])
            .Where(Directory.Exists)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .ToList();
    }

    public string? ResolveCurrentBeatmapPath()
    {
        var descriptor = ReadLatestWorkingBeatmap();
        if (descriptor is null)
        {
            Console.WriteLine("[beatmap-auto] current beatmap not found in osu!lazer runtime log");
            return null;
        }

        var current = descriptor.Value;
        Console.WriteLine($"[beatmap-auto] current={current.Display}");
        foreach (var candidate in EnumerateCandidateBeatmapFiles(_extraDataRoots))
        {
            var metadata = TryReadMetadata(candidate);
            if (metadata is null)
            {
                continue;
            }

            if (MatchesDescriptor(metadata.Value, current))
            {
                Console.WriteLine($"[beatmap-auto] matched {candidate}");
                return candidate;
            }
        }

        Console.WriteLine("[beatmap-auto] matching .osu file not found");
        return null;
    }

    private BeatmapDescriptor? ReadLatestWorkingBeatmap()
    {
        foreach (var logPath in EnumerateRuntimeLogs()
                     .OrderByDescending(File.GetLastWriteTimeUtc))
        {
            var lines = ReadTailLines(logPath, 600);
            for (var i = lines.Count - 1; i >= 0; i--)
            {
                var match = WorkingBeatmapRegex.Match(lines[i]);
                if (!match.Success)
                {
                    continue;
                }

                var display = match.Groups["display"].Value.Trim();
                var displayMatch = DisplayRegex.Match(display);
                if (!displayMatch.Success)
                {
                    return new BeatmapDescriptor(display, string.Empty, string.Empty, string.Empty, string.Empty);
                }

                return new BeatmapDescriptor(
                    display,
                    displayMatch.Groups["artist"].Value,
                    displayMatch.Groups["title"].Value,
                    displayMatch.Groups["creator"].Value,
                    displayMatch.Groups["version"].Value);
            }
        }

        return null;
    }

    private IEnumerable<string> EnumerateRuntimeLogs()
    {
        foreach (var dir in EnumerateLogsDirs(_extraDataRoots))
        {
            foreach (var log in Directory.EnumerateFiles(dir, "*.runtime.log"))
            {
                yield return log;
            }
        }
    }

    private static IEnumerable<string> EnumerateLogsDirs(IEnumerable<string> extraDataRoots)
    {
        var defaultLogsDir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "osu",
            "logs");
        if (Directory.Exists(defaultLogsDir))
        {
            yield return defaultLogsDir;
        }

        foreach (var root in extraDataRoots)
        {
            var logsDir = Path.Combine(root, "logs");
            if (Directory.Exists(logsDir))
            {
                yield return logsDir;
            }
        }
    }

    private static IEnumerable<string> EnumerateCandidateBeatmapFiles(IEnumerable<string> extraDataRoots)
    {
        var projectRoot = FindProjectRoot();
        if (projectRoot is not null)
        {
            var rawMaps = Path.Combine(projectRoot, "data", "raw", "osu");
            if (Directory.Exists(rawMaps))
            {
                foreach (var path in Directory.EnumerateFiles(rawMaps, "*.osu", SearchOption.AllDirectories))
                {
                    yield return path;
                }
            }
        }

        var lazerFiles = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
            "osu",
            "files");
        foreach (var path in EnumeratePotentialBeatmapFiles(lazerFiles))
        {
            yield return path;
        }

        foreach (var root in extraDataRoots)
        {
            foreach (var path in EnumeratePotentialBeatmapFiles(Path.Combine(root, "files")))
            {
                yield return path;
            }
        }
    }

    private static IEnumerable<string> EnumeratePotentialBeatmapFiles(string filesRoot)
    {
        if (!Directory.Exists(filesRoot))
        {
            yield break;
        }

        foreach (var path in Directory.EnumerateFiles(filesRoot, "*", SearchOption.AllDirectories))
        {
            FileInfo info;
            try
            {
                info = new FileInfo(path);
            }
            catch
            {
                continue;
            }

            if (info.Length is < 128 or > 2_000_000)
            {
                continue;
            }

            yield return path;
        }
    }

    private static BeatmapMetadata? TryReadMetadata(string path)
    {
        string text;
        try
        {
            text = File.ReadAllText(path);
        }
        catch
        {
            return null;
        }

        if (!text.Contains("osu file format", StringComparison.OrdinalIgnoreCase)
            || !text.Contains("[HitObjects]", StringComparison.OrdinalIgnoreCase))
        {
            return null;
        }

        var values = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var inMetadata = false;
        foreach (var rawLine in text.Split('\n'))
        {
            var line = rawLine.Trim();
            if (line.StartsWith('[') && line.EndsWith(']'))
            {
                inMetadata = string.Equals(line, "[Metadata]", StringComparison.OrdinalIgnoreCase);
                continue;
            }

            if (!inMetadata || string.IsNullOrWhiteSpace(line) || line.StartsWith("//"))
            {
                continue;
            }

            var separator = line.IndexOf(':');
            if (separator <= 0)
            {
                continue;
            }

            values[line[..separator].Trim()] = line[(separator + 1)..].Trim();
        }

        return new BeatmapMetadata(
            values.GetValueOrDefault("Artist", string.Empty),
            values.GetValueOrDefault("Title", string.Empty),
            values.GetValueOrDefault("Creator", string.Empty),
            values.GetValueOrDefault("Version", string.Empty));
    }

    private static bool MatchesDescriptor(BeatmapMetadata metadata, BeatmapDescriptor descriptor)
    {
        if (!string.IsNullOrWhiteSpace(descriptor.Artist)
            && !EqualsNormalized(metadata.Artist, descriptor.Artist))
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(descriptor.Title)
            && !EqualsNormalized(metadata.Title, descriptor.Title))
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(descriptor.Creator)
            && !EqualsNormalized(metadata.Creator, descriptor.Creator))
        {
            return false;
        }

        if (!string.IsNullOrWhiteSpace(descriptor.Version)
            && !EqualsNormalized(metadata.Version, descriptor.Version))
        {
            return false;
        }

        return true;
    }

    private static bool EqualsNormalized(string left, string right)
        => string.Equals(Normalize(left), Normalize(right), StringComparison.OrdinalIgnoreCase);

    private static string Normalize(string value)
        => new(value.Where(char.IsLetterOrDigit).Select(char.ToLowerInvariant).ToArray());

    private static string? FindProjectRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            if (Directory.Exists(Path.Combine(current.FullName, "src"))
                && Directory.Exists(Path.Combine(current.FullName, "external")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return null;
    }

    private static List<string> ReadTailLines(string path, int maxLines)
    {
        try
        {
            return File.ReadLines(path).TakeLast(maxLines).ToList();
        }
        catch
        {
            return [];
        }
    }

    private readonly record struct BeatmapDescriptor(
        string Display,
        string Artist,
        string Title,
        string Creator,
        string Version);

    private readonly record struct BeatmapMetadata(
        string Artist,
        string Title,
        string Creator,
        string Version);
}
