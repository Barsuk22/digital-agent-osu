namespace OsuAgentStudio;

internal static class StudioPaths
{
    public static string ProjectRoot => FindProjectRoot();
    public static string ControllerProject => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "OsuLazerController.csproj");
    public static string ControllerDebugExe => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "bin", "Debug", "net8.0-windows", "OsuLazerController.exe");
    public static string ControllerReleasePublishExe => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "bin", "Release", "net8.0-windows", "win-x64", "publish", "OsuLazerController.exe");
    public static string ControllerReleaseExe => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "bin", "Release", "net8.0-windows", "win-x64", "OsuLazerController.exe");
    public static string ControllerConfigsDir => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "configs");
    public static string AgentConfig => Path.Combine(ControllerConfigsDir, "runtime.onnx.live_play.agent_observed.json");
    public static string OracleConfig => Path.Combine(ControllerConfigsDir, "runtime.oracle.live_play.json");
    public static string CheckpointsDir => Path.Combine(ProjectRoot, "artifacts", "runs", "osu_lazer_transfer_generalization", "checkpoints");
    public static string LatestCheckpoint => Path.Combine(CheckpointsDir, "latest_lazer_transfer.pt");
    public static string BestCheckpoint => Path.Combine(CheckpointsDir, "best_lazer_transfer.pt");
    public static string OnnxOutput => Path.Combine(ProjectRoot, "artifacts", "exports", "onnx", "lazer_transfer_generalization.onnx");
    public static string LogsDir => Path.Combine(ProjectRoot, "external", "osu_lazer_controller", "bin", "Debug", "net8.0-windows", "logs");
    public static string MapsDir => Path.Combine(ProjectRoot, "data", "raw", "osu", "maps");

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

        return "dotnet";
    }

    private static string FindProjectRoot()
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

        var fallback = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        return Directory.Exists(Path.Combine(fallback, "src")) ? fallback : Environment.CurrentDirectory;
    }
}
