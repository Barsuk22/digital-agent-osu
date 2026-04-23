using System.Text.Json;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Beatmaps;

public sealed class BridgeBeatmapLoader
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    public BridgeBeatmap Load(string path)
    {
        var json = File.ReadAllText(path);
        return JsonSerializer.Deserialize<BridgeBeatmap>(json, JsonOptions)
               ?? throw new InvalidOperationException($"Failed to deserialize bridge beatmap: {path}");
    }
}
