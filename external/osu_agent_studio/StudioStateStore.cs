using System.Text.Json;

namespace OsuAgentStudio;

internal sealed class StudioState
{
    public int WindowX { get; set; }
    public int WindowY { get; set; }
    public int WindowWidth { get; set; } = 1360;
    public int WindowHeight { get; set; } = 840;
    public bool WindowMaximized { get; set; } = true;
    public string MapsFolder { get; set; } = StudioPaths.MapsDir;
    public int Updates { get; set; } = 500;
    public int SaveEvery { get; set; } = 10;
    public decimal CursorSpeed { get; set; } = 10.5m;
    public decimal LearningRate { get; set; } = 0.00003m;
    public bool ResetBest { get; set; } = false;
    public string SelectedConfigPath { get; set; } = StudioPaths.AgentConfig;
    public int SelectedTabIndex { get; set; }
    public List<string> SelectedMaps { get; set; } = [];
}

internal static class StudioStateStore
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        WriteIndented = true,
    };

    private static string StatePath =>
        Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "OsuAgentStudio",
            "studio_state.json");

    public static StudioState Load()
    {
        try
        {
            if (!File.Exists(StatePath))
            {
                return new StudioState();
            }

            var json = File.ReadAllText(StatePath);
            var state = JsonSerializer.Deserialize<StudioState>(json, JsonOptions) ?? new StudioState();
            Normalize(state);
            return state;
        }
        catch
        {
            return new StudioState();
        }
    }

    public static void Save(StudioState state)
    {
        try
        {
            Normalize(state);
            Directory.CreateDirectory(Path.GetDirectoryName(StatePath)!);
            File.WriteAllText(StatePath, JsonSerializer.Serialize(state, JsonOptions));
        }
        catch
        {
            // Best-effort persistence only.
        }
    }

    private static void Normalize(StudioState state)
    {
        state.WindowWidth = Math.Max(1180, state.WindowWidth);
        state.WindowHeight = Math.Max(760, state.WindowHeight);
        if (string.IsNullOrWhiteSpace(state.MapsFolder))
        {
            state.MapsFolder = StudioPaths.MapsDir;
        }

        state.Updates = Math.Clamp(state.Updates, 1, 100000);
        state.SaveEvery = Math.Clamp(state.SaveEvery, 10, 1000);
        state.CursorSpeed = state.CursorSpeed < 5m ? 10.5m : Math.Clamp(state.CursorSpeed, 5m, 40m);
        state.LearningRate = state.LearningRate < 0.000003m ? 0.00003m : Math.Clamp(state.LearningRate, 0.000003m, 0.01m);
        state.SelectedTabIndex = Math.Clamp(state.SelectedTabIndex, 0, 3);
        state.SelectedConfigPath = string.IsNullOrWhiteSpace(state.SelectedConfigPath)
            ? StudioPaths.AgentConfig
            : state.SelectedConfigPath;
        state.SelectedMaps ??= [];
    }
}
