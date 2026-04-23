using System.Diagnostics;
using System.Runtime.InteropServices;
using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Timing;

public sealed class MapTimer
{
    private readonly TimingConfig _config;
    private readonly Stopwatch _stopwatch = new();

    public MapTimer(TimingConfig config)
    {
        _config = config;
    }

    public async Task StartAsync(
        Func<string>? windowTitleProvider = null,
        BridgeBeatmap? beatmap = null,
        CancellationToken cancellationToken = default)
    {
        if (string.Equals(_config.StartTriggerMode, "hotkey", StringComparison.OrdinalIgnoreCase))
        {
            Console.WriteLine($"[timer] waiting for hotkey {_config.StartHotkey}...");
            if (!TryReadVirtualKey(_config.StartHotkey, out var virtualKey))
            {
                throw new InvalidOperationException($"Unsupported hotkey: {_config.StartHotkey}");
            }

            // Debounce: wait until the hotkey is released first, then react only to a fresh press.
            while (!cancellationToken.IsCancellationRequested && IsKeyDown(virtualKey))
            {
                await Task.Delay(25, cancellationToken);
            }

            while (!cancellationToken.IsCancellationRequested)
            {
                if (IsKeyDown(virtualKey))
                {
                    break;
                }

                await Task.Delay(25, cancellationToken);
            }
        }
        else if (string.Equals(_config.StartTriggerMode, "window_title", StringComparison.OrdinalIgnoreCase))
        {
            if (windowTitleProvider is null || beatmap is null)
            {
                throw new InvalidOperationException("window_title start mode requires window title provider and beatmap.");
            }

            Console.WriteLine("[timer] waiting for map title in window...");
            while (!cancellationToken.IsCancellationRequested)
            {
                var title = windowTitleProvider() ?? string.Empty;
                if (TitleMatchesBeatmap(title, beatmap))
                {
                    break;
                }

                await Task.Delay(150, cancellationToken);
            }

            if (_config.StartupDelayMs > 0)
            {
                await Task.Delay(TimeSpan.FromMilliseconds(_config.StartupDelayMs), cancellationToken);
            }
        }
        else if (_config.StartupDelayMs > 0)
        {
            await Task.Delay(TimeSpan.FromMilliseconds(_config.StartupDelayMs), cancellationToken);
        }

        _stopwatch.Restart();
    }

    public double CurrentTimeMs()
    {
        return _config.DiagnosticInitialMapTimeMs
               + _stopwatch.Elapsed.TotalMilliseconds
               + _config.AudioOffsetMs
               + _config.InputDelayMs
               + _config.CaptureDelayMs;
    }

    private static bool TryReadVirtualKey(string hotkey, out int virtualKey)
    {
        virtualKey = hotkey.ToUpperInvariant() switch
        {
            "F1" => 0x70,
            "F2" => 0x71,
            "F3" => 0x72,
            "F4" => 0x73,
            "F5" => 0x74,
            "F6" => 0x75,
            "F7" => 0x76,
            "F8" => 0x77,
            "F9" => 0x78,
            "F10" => 0x79,
            "F11" => 0x7A,
            "F12" => 0x7B,
            _ => 0,
        };

        return virtualKey != 0;
    }

    private static bool IsKeyDown(int virtualKey) => (GetAsyncKeyState(virtualKey) & 0x8000) != 0;

    private static bool TitleMatchesBeatmap(string title, BridgeBeatmap beatmap)
    {
        var normalizedTitle = Normalize(title);
        var beatmapTitle = Normalize(beatmap.Title);
        var beatmapVersion = Normalize(beatmap.Version);

        return normalizedTitle.Contains(beatmapTitle, StringComparison.OrdinalIgnoreCase)
               && normalizedTitle.Contains(beatmapVersion, StringComparison.OrdinalIgnoreCase);
    }

    private static string Normalize(string value)
        => new(value.Where(char.IsLetterOrDigit).Select(char.ToLowerInvariant).ToArray());

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int vKey);
}
