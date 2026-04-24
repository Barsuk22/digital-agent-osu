using OsuLazerController.Config;
using OsuLazerController.Models;
using OsuLazerController.Runtime.Bridge;
using OsuLazerController.Runtime.Beatmaps;
using OsuLazerController.Runtime.Capture;
using OsuLazerController.Runtime.Geometry;
using OsuLazerController.Runtime.Input;
using OsuLazerController.Runtime.Logging;
using OsuLazerController.Runtime.Timing;
using OsuLazerController.Runtime.Windowing;
using OsuLazerController.Runtime.Win32;
using System.Diagnostics;

namespace OsuLazerController.Runtime;

public sealed class ControllerApplication
{
    private readonly RuntimeConfig _config;

    public ControllerApplication(RuntimeConfig config)
    {
        _config = config;
    }

    public async Task<int> RunAsync()
    {
        Directory.CreateDirectory(Path.Combine(AppContext.BaseDirectory, _config.Logging.Directory));
        LivePlayfieldCalibration.Initialize(_config.Control);
        var osuDataRoots = ResolveOsuDataRoots();
        foreach (var root in osuDataRoots)
        {
            Console.WriteLine($"[osu-data] {root}");
        }

        using var logger = new TraceLogger(_config);
        using var bridge = CreatePolicyBridge();
        var windowLocator = new WindowLocator(_config.Window);
        var windowActivator = new WindowActivator();
        var playfieldMapper = new PlayfieldMapper(
            _config.Control.PlayfieldPadX,
            _config.Control.PlayfieldPadY,
            _config.Control.PlayfieldScaleX,
            _config.Control.PlayfieldScaleY,
            _config.Control.PlayfieldOffsetX,
            _config.Control.PlayfieldOffsetY);
        var mouseController = new MouseController(
            _config.Control.PlayfieldPadX,
            _config.Control.PlayfieldPadY,
            _config.Control.PlayfieldScaleX,
            _config.Control.PlayfieldScaleY,
            _config.Control.PlayfieldOffsetX,
            _config.Control.PlayfieldOffsetY);
        var beatmapLoader = new BridgeBeatmapLoader();
        var capture = new ScreenCapture();
        var frameRecorder = new VisionFrameRecorder(_config);
        using var datasetRecorder = new VisionDatasetRecorder(_config);
        var loop = new ControlLoop(_config, bridge, logger, mouseController, frameRecorder, datasetRecorder);
        Console.WriteLine("[startup] osu!lazer controller skeleton");
        Console.WriteLine($"[policy] {_config.PolicyBridge.Mode} {_config.PolicyBridge.Address}");
        Console.WriteLine($"[timing] {_config.Timing.TickRateHz:0.##} Hz");

        var window = await EnsureGameWindowAsync(windowLocator);
        if (window is not null)
        {
            if (_config.Window.RequireForeground)
            {
                windowActivator.Activate(window.Handle);
                await Task.Delay(600);
                window = windowLocator.FindGameWindow() ?? window;
            }

            Console.WriteLine(
                $"[window] pid={window.ProcessId} title=\"{window.Title}\" " +
                $"window={window.Left},{window.Top} {window.Width}x{window.Height} " +
                $"client={window.ClientLeft},{window.ClientTop} {window.ClientWidth}x{window.ClientHeight}");

            var playfield = playfieldMapper.Compute(window);
            var center = playfieldMapper.MapOsuToScreen(playfield, 256.0, 192.0);
            Console.WriteLine(
                $"[playfield] left={playfield.Left} top={playfield.Top} " +
                $"size={playfield.Width}x{playfield.Height} center=({center.ScreenX:0.0},{center.ScreenY:0.0}) " +
                $"pad=({_config.Control.PlayfieldPadX:0.#},{_config.Control.PlayfieldPadY:0.#}) " +
                $"scale=({_config.Control.PlayfieldScaleX:0.###},{_config.Control.PlayfieldScaleY:0.###}) " +
                $"offset=({_config.Control.PlayfieldOffsetX:0.#},{_config.Control.PlayfieldOffsetY:0.#})");
            LivePlayfieldCalibration.PrintHelp();
            if (frameRecorder.Enabled)
            {
                var visionConfig = _config.VisionCapture ?? VisionCaptureConfig.Disabled();
                Console.WriteLine(
                    $"[vision] enabled size={visionConfig.Width}x{visionConfig.Height} " +
                    $"grayscale={visionConfig.Grayscale} captureEveryTicks={visionConfig.CaptureEveryNTicks} " +
                        $"maxCapturedFrames={visionConfig.MaxCapturedFrames} saveFrames={visionConfig.SaveFrames} " +
                        $"saveEveryTicks={visionConfig.SaveEveryNTicks} maxSavedFrames={visionConfig.MaxSavedFrames}");
            }
            if (datasetRecorder.Enabled)
            {
                var datasetConfig = _config.VisionDataset ?? VisionDatasetConfig.Disabled();
                Console.WriteLine(
                    $"[vision-dataset] enabled dir={datasetConfig.Directory} " +
                    $"saveEveryTicks={datasetConfig.SaveEveryNTicks} maxFrames={datasetConfig.MaxFrames}");
            }

            var screenshotPath = Path.Combine(
                AppContext.BaseDirectory,
                _config.Logging.Directory,
                $"osu_client_{DateTime.UtcNow:yyyyMMdd_HHmmss}.png");
            capture.CaptureClientArea(window, screenshotPath);
            Console.WriteLine($"[capture] {screenshotPath}");

            // Safe diagnostic: compute mapping without moving yet. Once live control starts,
            // MouseController will consume the same mapping.
            _ = mouseController;
        }
        else
        {
            Console.WriteLine("[window] not found");
        }

        var result = await loop.RunWarmupAsync();
        Console.WriteLine($"[warmup] ok={result.Ok} policyLatencyMs={result.PolicyLatencyMs:0.###}");

        if (window is not null && UsesAutoBeatmapWithOsuLogStart())
        {
            while (true)
            {
                Console.WriteLine("[timer] waiting for osu!lazer gameplay clock before resolving auto beatmap...");
                var watcher = new OsuLazerRuntimeLogWatcher(ResolveOsuLogsDirs(osuDataRoots));
                var start = await watcher.WaitForGameplayClockStartAsync(CancellationToken.None);
                var sessionTimer = new MapTimer(_config.Timing);
                sessionTimer.StartFromOsuLog(watcher, start.SeekTimeMs);

                PrepareBeatmapExportIfNeeded(osuDataRoots);
                if (!TryLoadBeatmap(beatmapLoader, out var sessionBeatmap))
                {
                    continue;
                }

                var sessionWindow = windowLocator.FindGameWindow() ?? window;
                await loop.RunDiagnosticTicksAsync(
                    sessionBeatmap!,
                    sessionWindow,
                    () => windowLocator.FindGameWindow()?.Title ?? sessionWindow.Title,
                    sessionTimer);
            }
        }

        PrepareBeatmapExportIfNeeded(osuDataRoots);
        if (TryLoadBeatmap(beatmapLoader, out var beatmap) && window is not null)
        {
            await loop.RunDiagnosticTicksAsync(
                beatmap!,
                window,
                () => windowLocator.FindGameWindow()?.Title ?? window.Title);
        }

        frameRecorder.PrintSummary();
        datasetRecorder.PrintSummary();

        return result.Ok ? 0 : 1;
    }

    private void PrepareBeatmapExportIfNeeded(IReadOnlyList<string> osuDataRoots)
    {
        var sourcePath = _config.Beatmap.SourceOsuPath;
        if (string.Equals(sourcePath, "auto", StringComparison.OrdinalIgnoreCase))
        {
            sourcePath = new OsuLazerCurrentBeatmapResolver(osuDataRoots).ResolveCurrentBeatmapPath();
            if (string.IsNullOrWhiteSpace(sourcePath))
            {
                Console.WriteLine("[beatmap-auto] falling back to existing bridge export");
                return;
            }
        }

        if (string.IsNullOrWhiteSpace(sourcePath) || !File.Exists(sourcePath))
        {
            return;
        }

        if (!string.Equals(sourcePath, _config.Beatmap.SourceOsuPath, StringComparison.OrdinalIgnoreCase)
            || !File.Exists(_config.Beatmap.ExportJsonPath))
        {
            _ = new BridgeBeatmapExporter().TryExport(sourcePath, _config.Beatmap.ExportJsonPath);
        }
    }

    private bool UsesAutoBeatmapWithOsuLogStart()
        => string.Equals(_config.Beatmap.SourceOsuPath, "auto", StringComparison.OrdinalIgnoreCase)
           && string.Equals(_config.Timing.StartTriggerMode, "osu_log", StringComparison.OrdinalIgnoreCase);

    private IReadOnlyList<string> ResolveOsuDataRoots()
    {
        var roots = new List<string>();
        AddIfExists(roots, Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "osu"));
        AddIfExists(roots, Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "osu-gu"));

        if (!string.IsNullOrWhiteSpace(_config.Window.ExecutablePath))
        {
            var executableDir = Path.GetDirectoryName(_config.Window.ExecutablePath);
            if (!string.IsNullOrWhiteSpace(executableDir))
            {
                var dir = new DirectoryInfo(executableDir);
                while (dir is not null)
                {
                    if (File.Exists(Path.Combine(dir.FullName, ".portable"))
                        || Directory.Exists(Path.Combine(dir.FullName, "files")))
                    {
                        AddIfExists(roots, dir.FullName);
                        break;
                    }

                    dir = dir.Parent;
                }
            }
        }

        return roots;
    }

    private static IEnumerable<string> ResolveOsuLogsDirs(IEnumerable<string> dataRoots)
        => dataRoots
            .Select(root => Path.Combine(root, "logs"))
            .Where(Directory.Exists);

    private static void AddIfExists(List<string> roots, string path)
    {
        if (Directory.Exists(path) && !roots.Contains(path, StringComparer.OrdinalIgnoreCase))
        {
            roots.Add(path);
        }
    }

    private bool TryLoadBeatmap(BridgeBeatmapLoader beatmapLoader, out BridgeBeatmap? beatmap)
    {
        beatmap = null;
        if (!File.Exists(_config.Beatmap.ExportJsonPath))
        {
            Console.WriteLine($"[beatmap] export json not found: {_config.Beatmap.ExportJsonPath}");
            return false;
        }

        beatmap = beatmapLoader.Load(_config.Beatmap.ExportJsonPath);
        Console.WriteLine(
            $"[beatmap] {beatmap.Artist} - {beatmap.Title} [{beatmap.Version}] " +
            $"objects={beatmap.HitObjects.Count} timingPoints={beatmap.TimingPoints.Count}");
        return true;
    }

    private IPolicyBridge CreatePolicyBridge()
    {
        return _config.PolicyBridge.Mode.ToLowerInvariant() switch
        {
            "zeromq" => new ZeroMqPolicyBridge(_config.PolicyBridge),
            "onnx" => new OnnxPolicyBridge(_config.PolicyBridge),
            "oracle" => new NoopPolicyBridge(),
            _ => throw new InvalidOperationException($"Unsupported policy bridge mode: {_config.PolicyBridge.Mode}"),
        };
    }

    private async Task<WindowInfo?> EnsureGameWindowAsync(WindowLocator windowLocator)
    {
        RestoreExistingGameWindows();

        var window = windowLocator.FindGameWindow();
        if (window is not null)
        {
            return window;
        }

        if (!string.IsNullOrWhiteSpace(_config.Window.ExecutablePath) && File.Exists(_config.Window.ExecutablePath))
        {
            Console.WriteLine($"[window] not found, starting {_config.Window.ExecutablePath}");
            Process.Start(new ProcessStartInfo
            {
                FileName = _config.Window.ExecutablePath,
                UseShellExecute = true,
                WorkingDirectory = Path.GetDirectoryName(_config.Window.ExecutablePath) ?? AppContext.BaseDirectory,
            });

            for (var attempt = 0; attempt < 40; attempt++)
            {
                await Task.Delay(500);
                window = windowLocator.FindGameWindow();
                if (window is not null)
                {
                    return window;
                }
            }
        }

        return null;
    }

    private void RestoreExistingGameWindows()
    {
        foreach (var process in Process.GetProcesses())
        {
            try
            {
                if (!MatchesHint(process.ProcessName, _config.Window.ProcessName))
                {
                    continue;
                }

                if (process.MainWindowHandle == nint.Zero)
                {
                    continue;
                }

                _ = NativeMethods.ShowWindow(process.MainWindowHandle, NativeMethods.SW_RESTORE);
            }
            catch
            {
                // Ignore transient or inaccessible processes.
            }
        }
    }

    private static bool MatchesHint(string candidate, string hint)
    {
        if (string.IsNullOrWhiteSpace(hint))
        {
            return true;
        }

        return Normalize(candidate).Contains(Normalize(hint), StringComparison.OrdinalIgnoreCase);
    }

    private static string Normalize(string value)
        => new(value.Where(char.IsLetterOrDigit).Select(char.ToLowerInvariant).ToArray());
}
