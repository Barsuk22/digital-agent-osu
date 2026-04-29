using System.Diagnostics;
using System.Globalization;

namespace OsuAgentStudio.Core;

public sealed class StudioService
{
    private readonly ManagedProcess _controller = new();
    private readonly ManagedProcess _training = new();
    private readonly ManagedProcess _export = new();
    private readonly string _logFilePath = StudioPaths.StudioRuntimeLog;

    public StudioService()
    {
        WireProcess(_controller, "agent");
        WireProcess(_training, "training");
        WireProcess(_export, "export");
    }

    public event Action<string>? LogReceived;
    public event Action<string, string>? StatusChanged;

    public bool IsControllerRunning => _controller.IsRunning;
    public bool IsTrainingRunning => _training.IsRunning;
    public bool IsExportRunning => _export.IsRunning;

    public IReadOnlyList<ConfigItem> RefreshConfigList()
    {
        if (!Directory.Exists(StudioPaths.ControllerConfigsDir))
            return [];

        return Directory.GetFiles(StudioPaths.ControllerConfigsDir, "*.json")
            .OrderBy(Path.GetFileName)
            .Select(path => new ConfigItem(path))
            .ToList();
    }

    public IReadOnlyList<MapItem> ScanMaps(string mapsFolder, IReadOnlyCollection<string>? selectedPaths = null)
    {
        selectedPaths ??= [];
        var selectedLookup = new HashSet<string>(selectedPaths.Where(File.Exists), StringComparer.OrdinalIgnoreCase);

        if (!Directory.Exists(mapsFolder))
        {
            AppendLog($"Maps folder not found: {mapsFolder}");
            return [];
        }

        var result = new List<MapItem>();
        foreach (var path in Directory.EnumerateFiles(mapsFolder, "*.osu", SearchOption.AllDirectories).OrderBy(Path.GetFileName))
        {
            var selected = selectedLookup.Contains(path)
                || (selectedLookup.Count == 0 && IsDefaultTrainingMap(path));
            result.Add(new MapItem(path, selected));
        }

        AppendLog($"Maps scanned: {result.Count}, selected: {result.Count(item => item.IsSelected)}.");
        return result;
    }

    public void StartController(string configPath)
    {
        if (!File.Exists(configPath))
        {
            AppendLog($"Config not found: {configPath}");
            return;
        }

        StopOrphanedControllerProcesses();
        var launcher = StudioPaths.ResolveControllerLaunchPath();
        if (string.Equals(launcher, "dotnet", StringComparison.OrdinalIgnoreCase))
        {
            _controller.Start("agent", "dotnet", ["run", "--project", StudioPaths.ControllerProject, "--", configPath], StudioPaths.ProjectRoot);
            return;
        }

        var workingDir = Path.GetDirectoryName(launcher) ?? StudioPaths.ProjectRoot;
        _controller.Start("agent", launcher, [configPath], workingDir);
    }

    public void StopControllerProcesses()
    {
        _controller.Stop("agent");
        StopOrphanedControllerProcesses();
        StatusChanged?.Invoke("agent", IsControllerRunning ? "Running" : "Idle");
    }

    public void StartTraining(TrainingOptions options)
    {
        if (!StudioPaths.IsTrainingFromSourceAvailable())
        {
            AppendLog("Training is not available in this build (no src/apps). Use full project or set OSUAGENTSTUDIO_PROJECT_ROOT.");
            return;
        }

        if (options.SelectedMaps.Count == 0)
        {
            AppendLog("No maps selected for training.");
            return;
        }

        var args = new List<string>
        {
            "-m", "src.apps.train_osu_lazer_transfer",
            "--run-name", StudioPaths.PrecisionRunName,
            "--source-checkpoint", StudioPaths.SourceBestCheckpoint,
            "--profile", "precision_spinner",
            // "--resume-latest",
            "--updates", options.Updates.ToString(CultureInfo.InvariantCulture),
            "--save-every", options.SaveEvery.ToString(CultureInfo.InvariantCulture),
            "--cursor-speed", options.CursorSpeed.ToString(CultureInfo.InvariantCulture),
            "--learning-rate", options.LearningRate.ToString(CultureInfo.InvariantCulture),
            "--maps-dir", options.MapsFolder,
        };

        foreach (var map in options.SelectedMaps)
        {
            args.Add("--map");
            args.Add(map);
        }

        if (options.ResetBest)
            args.Add("--reset-best");

        args.Insert(0, "-u");
        _training.Start("training", "python", args, StudioPaths.ProjectRoot);
    }

    public void StopTraining() => _training.Stop("training");

    public void ExportCheckpoint(string checkpoint)
    {
        if (!StudioPaths.IsExportFromSourceAvailable())
        {
            AppendLog("ONNX export needs Python project (src/apps/export_osu_policy_onnx). Not in test-only bundle.");
            return;
        }

        if (!File.Exists(checkpoint))
        {
            AppendLog($"Checkpoint not found: {checkpoint}");
            return;
        }

        _export.Start(
            "export",
            "python",
            ["-m", "src.apps.export_osu_policy_onnx", "--checkpoint", checkpoint, "--out", StudioPaths.OnnxOutput],
            StudioPaths.ProjectRoot);
    }

    public FileStatus GetFileStatus()
    {
        var latest = File.Exists(StudioPaths.LatestCheckpoint) ? File.GetLastWriteTime(StudioPaths.LatestCheckpoint).ToString("HH:mm") : "missing";
        var best = File.Exists(StudioPaths.BestCheckpoint)
            ? File.GetLastWriteTime(StudioPaths.BestCheckpoint).ToString("HH:mm")
            : File.Exists(StudioPaths.SourceBestCheckpoint)
                ? $"source {File.GetLastWriteTime(StudioPaths.SourceBestCheckpoint):HH:mm}"
                : "missing";
        return new FileStatus(latest, best);
    }

    public void OpenPath(string path)
    {
        if (!Directory.Exists(path) && !File.Exists(path))
            Directory.CreateDirectory(path);

        Process.Start(new ProcessStartInfo { FileName = path, UseShellExecute = true });
    }

    public void Shutdown()
    {
        _controller.Stop("agent");
        _training.Stop("training");
        _export.Stop("export");
    }

    public static bool IsDefaultTrainingMap(string path)
    {
        var name = Path.GetFileNameWithoutExtension(path).ToLowerInvariant();
        var blocked = new[] { "hard", "insane", "expert", "extra", "lunatic", "another", "hyper", "oni", "sample" };
        if (blocked.Any(name.Contains))
            return false;

        return name.Contains("beginner") || name.Contains("easy");
    }

    private void StopOrphanedControllerProcesses()
    {
        try
        {
            foreach (var process in Process.GetProcessesByName("OsuLazerController"))
            {
                try
                {
                    process.Kill(entireProcessTree: true);
                    AppendLog($"[agent] cleaned leftover controller pid={process.Id}.");
                }
                catch (Exception ex)
                {
                    AppendLog($"[agent] cleanup failed for pid={process.Id}: {ex.Message}");
                }
            }
        }
        catch (Exception ex)
        {
            AppendLog($"[agent] controller cleanup failed: {ex.Message}");
        }
    }

    private void WireProcess(ManagedProcess process, string key)
    {
        process.OutputReceived += AppendLog;
        process.StatusChanged += value =>
            StatusChanged?.Invoke(key, value.Replace(key, "", StringComparison.OrdinalIgnoreCase).Trim());
    }

    private void AppendLog(string line)
    {
        if (string.IsNullOrWhiteSpace(line))
            return;

        LogReceived?.Invoke(line);

        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_logFilePath)!);
            File.AppendAllText(_logFilePath, $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {line}{Environment.NewLine}");
        }
        catch
        {
            // Logging must never take the studio down.
        }
    }
}
