using System.Diagnostics;
using System.Runtime.InteropServices;
using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Timing;

public sealed class MapTimer
{
    private readonly TimingConfig _config;
    private readonly Stopwatch _stopwatch = new();
    private OsuLazerRuntimeLogWatcher? _logWatcher;
    private double _baseMapTimeMs;
    private double _liveAdjustmentMs;
    private bool _isPaused;
    private bool _sessionRestartRequested;
    private bool _f6WasDown;
    private bool _f7WasDown;
    private bool _f9WasDown;
    private bool _f10WasDown;
    private bool _f11WasDown;

    public MapTimer(TimingConfig config)
    {
        _config = config;
    }

    public void StartFromOsuLog(OsuLazerRuntimeLogWatcher watcher, double seekTimeMs)
    {
        _logWatcher = watcher;
        _baseMapTimeMs = seekTimeMs;
        _isPaused = false;
        _sessionRestartRequested = false;
        _stopwatch.Restart();
        Console.WriteLine($"[timer] using pre-detected osu!lazer gameplay clock seek={_baseMapTimeMs:0.0}ms");
        Console.WriteLine("[timer] live sync keys: F6=-25ms F7=+25ms F9=-100ms F10=+100ms F11=reset");
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
        else if (string.Equals(_config.StartTriggerMode, "osu_log", StringComparison.OrdinalIgnoreCase))
        {
            Console.WriteLine("[timer] waiting for osu!lazer gameplay clock start in runtime log...");
            _logWatcher = new OsuLazerRuntimeLogWatcher();
            var start = await _logWatcher.WaitForGameplayClockStartAsync(cancellationToken);
            _baseMapTimeMs = start.SeekTimeMs;
            Console.WriteLine($"[timer] osu!lazer gameplay clock start detected seek={_baseMapTimeMs:0.0}ms");
        }
        else if (_config.StartupDelayMs > 0)
        {
            await Task.Delay(TimeSpan.FromMilliseconds(_config.StartupDelayMs), cancellationToken);
        }

        _stopwatch.Restart();
        Console.WriteLine("[timer] live sync keys: F6=-25ms F7=+25ms F9=-100ms F10=+100ms F11=reset");
    }

    public double CurrentTimeMs()
    {
        PollLiveAdjustmentKeys();
        PollGameplayClockEvents();
        return _baseMapTimeMs
               + _config.DiagnosticInitialMapTimeMs
               + _stopwatch.Elapsed.TotalMilliseconds
               + _config.AudioOffsetMs
               + _config.InputDelayMs
               + _config.CaptureDelayMs
               + _liveAdjustmentMs;
    }

    public double LiveAdjustmentMs => _liveAdjustmentMs;

    public bool IsPaused => _isPaused;
    public bool SessionRestartRequested => _sessionRestartRequested;

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

    private void PollGameplayClockEvents()
    {
        if (_logWatcher is null)
        {
            return;
        }

        foreach (var clockEvent in _logWatcher.PollEvents())
        {
            if (clockEvent.Kind == GameplayClockEventKind.Seek)
            {
                if (_isPaused)
                {
                    _sessionRestartRequested = true;
                    Console.WriteLine($"[timer] osu!lazer seek while paused {_lastSeekLabel(clockEvent.SeekTimeMs)}; restarting session");
                    continue;
                }

                _baseMapTimeMs = clockEvent.SeekTimeMs;
                _stopwatch.Restart();
                _isPaused = false;
                Console.WriteLine($"[timer] osu!lazer seek sync {_baseMapTimeMs:0.0}ms");
                continue;
            }

            if (clockEvent.Kind == GameplayClockEventKind.Stop)
            {
                _stopwatch.Stop();
                _isPaused = true;
                Console.WriteLine("[timer] osu!lazer clock stopped; pausing current session");

                continue;
            }

            if (clockEvent.Kind == GameplayClockEventKind.Start)
            {
                if (_isPaused)
                {
                    _stopwatch.Start();
                    _isPaused = false;
                    Console.WriteLine("[timer] osu!lazer clock resumed; continuing current session");
                }
            }
        }
    }

    private void PollLiveAdjustmentKeys()
    {
        ApplyAdjustmentOnPress(0x75, ref _f6WasDown, -25.0);
        ApplyAdjustmentOnPress(0x76, ref _f7WasDown, 25.0);
        ApplyAdjustmentOnPress(0x78, ref _f9WasDown, -100.0);
        ApplyAdjustmentOnPress(0x79, ref _f10WasDown, 100.0);

        var f11Down = IsKeyDown(0x7A);
        if (f11Down && !_f11WasDown)
        {
            _liveAdjustmentMs = 0.0;
            Console.WriteLine("[timer] live adjustment reset to +0ms");
        }

        _f11WasDown = f11Down;
    }

    private void ApplyAdjustmentOnPress(int virtualKey, ref bool wasDown, double deltaMs)
    {
        var isDown = IsKeyDown(virtualKey);
        if (isDown && !wasDown)
        {
            _liveAdjustmentMs += deltaMs;
            Console.WriteLine($"[timer] live adjustment now {_liveAdjustmentMs:+0;-0;0}ms");
        }

        wasDown = isDown;
    }

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

    private static string _lastSeekLabel(double seekTimeMs) => $"{seekTimeMs:0.0}ms";
}
