namespace OsuAgentStudio;

internal static class StudioPaths
{
    public const string PrecisionRunName = "osu_lazer_precision_spinner_v2";

    /// <summary>Stable ONNX filename that <c>runtime.onnx.live_play.agent_observed.gu.json</c> points at.</summary>
    public const string LiveOnnxFileName = "lazer_transfer_generalization.onnx";

    public static string ProjectRoot => FindProjectRoot();
    public static string ControllerProject => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "OsuLazerController.csproj");
    public static string ControllerDebugExe => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "bin", "Debug", "net8.0-windows", "OsuLazerController.exe");
    public static string ControllerReleasePublishExe => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "bin", "Release", "net8.0-windows", "win-x64", "publish", "OsuLazerController.exe");
    public static string ControllerReleaseExe => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "bin", "Release", "net8.0-windows", "win-x64", "OsuLazerController.exe");
    public static string ControllerConfigsDir => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "configs");
    public static string AgentConfig => Path.Combine(ControllerConfigsDir, "runtime.onnx.live_play.agent_observed.gu.json");
    public static string OracleConfig => Path.Combine(ControllerConfigsDir, "runtime.oracle.live_play.json");
    public static string CheckpointsDir => Path.Combine(ProjectRoot, "artifacts", "runs", PrecisionRunName, "checkpoints");
    public static string LatestCheckpoint => Path.Combine(CheckpointsDir, "latest_lazer_transfer.pt");
    public static string BestCheckpoint => Path.Combine(CheckpointsDir, "best_lazer_transfer.pt");
    public static string OnnxOutput => Path.Combine(ProjectRoot, "artifacts", "exports", "onnx", LiveOnnxFileName);
    public static string LogsDir => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "bin", "Debug", "net8.0-windows", "logs");

    public static string StudioLogsDir => Path.Combine(ProjectRoot, "artifacts", "logs");
    public static string StudioRuntimeLog => Path.Combine(StudioLogsDir, "studio_runtime.log");

    /// <summary>Runtime logs: publish folder in test bundle, else dev Debug logs.</summary>
    public static string ResolveLogsDir()
    {
        var publishDir = Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "publish", "logs");
        if (Directory.Exists(publishDir))
        {
            return publishDir;
        }

        return LogsDir;
    }

    public static string MapsDir => Path.Combine(ProjectRoot, "data", "raw", "osu", "maps");

    public static string TrainScriptPath => Path.Combine(ProjectRoot, "src", "apps", "train_osu_lazer_transfer.py");

    public static string ExportScriptPath => Path.Combine(ProjectRoot, "src", "apps", "export_osu_policy_onnx.py");

    public static bool IsTrainingFromSourceAvailable() => File.Exists(TrainScriptPath);

    public static bool IsExportFromSourceAvailable() => File.Exists(ExportScriptPath);

    public static string ResolveControllerLaunchPath()
    {
        if (File.Exists(ControllerReleasePublishExe))
        {
            return ControllerReleasePublishExe;
        }

        if (File.Exists(ControllerReleaseExe))
        {
            return ControllerReleaseExe;
        }

        if (File.Exists(ControllerDebugExe))
        {
            return ControllerDebugExe;
        }

        var portablePublish = Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "publish", "OsuLazerController.exe");
        if (File.Exists(portablePublish))
        {
            return portablePublish;
        }

        return "dotnet";
    }

    private static string FindProjectRoot()
    {
        var fromEnv = Environment.GetEnvironmentVariable("OSUAGENTSTUDIO_PROJECT_ROOT");
        if (!string.IsNullOrWhiteSpace(fromEnv))
        {
            var p = Path.GetFullPath(fromEnv.Trim());
            if (IsLayoutProjectRoot(p))
            {
                return p;
            }
        }

        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            if (IsLayoutProjectRoot(current.FullName))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        var fallback = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        if (IsLayoutProjectRoot(fallback))
        {
            return fallback;
        }

        return Environment.CurrentDirectory;
    }

    private static bool IsLayoutProjectRoot(string directory)
    {
        if (string.IsNullOrWhiteSpace(directory) || !Directory.Exists(directory))
        {
            return false;
        }

        var extController = Path.Combine(directory, "external", "osu_lazer_controller");
        if (!Directory.Exists(extController))
        {
            return false;
        }

        return true;
    }
}
