namespace OsuAgentStudio.Core;

public sealed record ConfigItem(string Path)
{
    public string Name => System.IO.Path.GetFileName(Path);
    public override string ToString() => Name;
}

public sealed class MapItem
{
    public MapItem(string path, bool isSelected = false)
    {
        Path = path;
        IsSelected = isSelected;
    }

    public string Path { get; }
    public bool IsSelected { get; set; }

    public string DisplayName
    {
        get
        {
            var parent = Directory.GetParent(Path)?.Name ?? "";
            return $"{parent} / {System.IO.Path.GetFileName(Path)}";
        }
    }

    public override string ToString() => DisplayName;
}

public sealed record FileStatus(string LatestCheckpoint, string BestCheckpoint);

public sealed record TrainingOptions(
    int Updates,
    int SaveEvery,
    decimal CursorSpeed,
    decimal LearningRate,
    bool ResetBest,
    string MapsFolder,
    IReadOnlyCollection<string> SelectedMaps);
