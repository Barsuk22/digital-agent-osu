using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Beatmaps;

public sealed class UpcomingObjectSelector
{
    public IReadOnlyList<BridgeHitObject> SelectUpcoming(BridgeBeatmap beatmap, double currentTimeMs, int count)
    {
        var preempt = ArToPreemptMs(beatmap.Difficulty.Ar);
        return beatmap.HitObjects
            .Where(obj => ObjectEndTimeMs(obj) + 220.0 >= currentTimeMs)
            .Where(obj => obj.TimeMs - preempt <= currentTimeMs)
            .OrderBy(obj => obj.TimeMs)
            .Take(count)
            .ToList();
    }

    private static double ArToPreemptMs(double ar)
    {
        if (ar < 5.0)
        {
            return 1200.0 + 600.0 * (5.0 - ar) / 5.0;
        }

        return 1200.0 - 750.0 * (ar - 5.0) / 5.0;
    }

    private static double ObjectEndTimeMs(BridgeHitObject obj)
    {
        if (obj.Kind == "spinner" && obj.EndTimeMs.HasValue)
        {
            return obj.EndTimeMs.Value;
        }

        if (obj.Kind == "slider" && obj.DurationMs.HasValue)
        {
            return obj.TimeMs + obj.DurationMs.Value;
        }

        return obj.TimeMs;
    }
}
