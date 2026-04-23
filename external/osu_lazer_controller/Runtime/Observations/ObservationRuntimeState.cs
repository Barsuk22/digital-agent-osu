using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Observations;

public sealed class ObservationRuntimeState
{
    private const double SpinnerCenterX = 256.0;
    private const double SpinnerCenterY = 192.0;
    private const double SpinnerTargetRadius = 76.0;
    private const double SpinnerGoodRadiusTolerance = 26.0;
    private const double SpinnerMinValidRadius = 42.0;
    private const double SpinnerMaxValidRadius = 125.0;
    private const double SpinnerMaxDeltaPerStep = 0.50;
    private const double SpinnerMinDeltaPerStep = 0.025;
    private const double SpinnerTargetSpins = 2.0;

    public int ObjectIndex { get; private set; }
    public BridgeHitObject? ActiveSlider { get; private set; }
    public bool ActiveSliderHeadHit { get; private set; }

    public BridgeHitObject? ActiveSpinner { get; private set; }
    public double SpinnerSpinProgress { get; private set; }
    public double? LastSpinnerAngle { get; private set; }
    public double LastAngularVelocity { get; private set; }
    public double LastSpinnerTimeMs { get; private set; }
    public double SpinnerTargetSpinsValue => SpinnerTargetSpins;
    public bool LastRawClickDown { get; private set; }
    public bool JustPressed { get; private set; }

    public void Reset()
    {
        ObjectIndex = 0;
        ActiveSlider = null;
        ActiveSliderHeadHit = false;
        ActiveSpinner = null;
        LastRawClickDown = false;
        JustPressed = false;
        ResetSpinnerProgress();
    }

    public void Sync(BridgeBeatmap beatmap, double mapTimeMs)
    {
        ExpireMissedObjects(beatmap, mapTimeMs);

        if (ActiveSpinner is not null && (!ActiveSpinner.EndTimeMs.HasValue || mapTimeMs > ActiveSpinner.EndTimeMs.Value + 220.0))
        {
            ActiveSpinner = null;
            ResetSpinnerProgress();
        }
    }

    public IReadOnlyList<BridgeHitObject> PeekUpcoming(BridgeBeatmap beatmap, int count)
    {
        var result = new List<BridgeHitObject>(count);
        for (var index = ObjectIndex; index < beatmap.HitObjects.Count && result.Count < count; index++)
        {
            result.Add(beatmap.HitObjects[index]);
        }

        return result;
    }

    public void AdvancePostAction(
        BridgeBeatmap beatmap,
        double mapTimeMs,
        double cursorX,
        double cursorY,
        bool rawClickDown,
        bool clickDown,
        double dtMs)
    {
        Sync(beatmap, mapTimeMs);
        JustPressed = rawClickDown && !LastRawClickDown;

        if (HasActiveSliderEnded(mapTimeMs))
        {
            ActiveSlider = null;
            ActiveSliderHeadHit = false;
        }

        if (ActiveSpinner is null && ObjectIndex < beatmap.HitObjects.Count)
        {
            var current = beatmap.HitObjects[ObjectIndex];
            if (current.Kind == "spinner" && current.EndTimeMs.HasValue && mapTimeMs >= current.TimeMs)
            {
                ActiveSpinner = current;
                ObjectIndex += 1;
                ResetSpinnerProgress();
            }
        }

        if (ActiveSlider is null && JustPressed && ObjectIndex < beatmap.HitObjects.Count)
        {
            var current = beatmap.HitObjects[ObjectIndex];
            var timingError = Math.Abs(mapTimeMs - current.TimeMs);
            var radius = OsuCircleRadius(beatmap.Difficulty.Cs);
            var dist = Distance(cursorX, cursorY, current.X, current.Y);

            if (current.Kind == "circle" && timingError <= HitWindow50(beatmap.Difficulty.Od) && dist <= radius)
            {
                ObjectIndex += 1;
            }
            else if (current.Kind == "slider"
                     && current.DurationMs.HasValue
                     && timingError <= HitWindow50(beatmap.Difficulty.Od)
                     && dist <= radius)
            {
                ActiveSlider = current;
                ActiveSliderHeadHit = true;
                ObjectIndex += 1;
            }
        }

        if (ActiveSpinner is null)
        {
            LastRawClickDown = rawClickDown;
            ResetSpinnerProgress();
            return;
        }

        var angle = Math.Atan2(cursorY - SpinnerCenterY, cursorX - SpinnerCenterX);
        var radiusValue = Distance(cursorX, cursorY, SpinnerCenterX, SpinnerCenterY);
        var radiusError = Math.Abs(radiusValue - SpinnerTargetRadius);
        var validRadius = radiusValue >= SpinnerMinValidRadius && radiusValue <= SpinnerMaxValidRadius;
        var goodRadius = radiusError <= SpinnerGoodRadiusTolerance;

        if (LastSpinnerAngle.HasValue)
        {
            var delta = angle - LastSpinnerAngle.Value;
            while (delta > Math.PI) delta -= 2.0 * Math.PI;
            while (delta < -Math.PI) delta += 2.0 * Math.PI;

            var deltaAbs = Math.Abs(delta);
            var tooFast = deltaAbs > SpinnerMaxDeltaPerStep;
            var effectiveDelta = Math.Min(deltaAbs, SpinnerMaxDeltaPerStep);
            if (clickDown && validRadius && !tooFast && effectiveDelta >= SpinnerMinDeltaPerStep)
            {
                SpinnerSpinProgress += effectiveDelta;
            }

            LastAngularVelocity = deltaAbs / Math.Max(1e-6, dtMs / 1000.0);
            if (!clickDown || !goodRadius)
            {
                LastAngularVelocity *= 0.85;
            }
        }
        else
        {
            LastAngularVelocity = 0.0;
        }

        LastSpinnerAngle = angle;
        LastSpinnerTimeMs = mapTimeMs;
        LastRawClickDown = rawClickDown;
    }

    private void ExpireMissedObjects(BridgeBeatmap beatmap, double mapTimeMs)
    {
        while (ObjectIndex < beatmap.HitObjects.Count)
        {
            var current = beatmap.HitObjects[ObjectIndex];
            if (current.Kind == "spinner")
            {
                break;
            }

            if (current.Kind == "slider" && ActiveSlider is not null)
            {
                break;
            }

            var missDeadline = current.TimeMs + HitWindow50(beatmap.Difficulty.Od);
            if (mapTimeMs <= missDeadline)
            {
                break;
            }

            if (current.Kind == "circle" || current.Kind == "slider")
            {
                ObjectIndex += 1;
                continue;
            }

            break;
        }
    }

    private void ResetSpinnerProgress()
    {
        SpinnerSpinProgress = 0.0;
        LastSpinnerAngle = null;
        LastAngularVelocity = 0.0;
        LastSpinnerTimeMs = 0.0;
    }

    private static double HitWindow50(double od) => 199.5 - 10.0 * od;

    private bool HasActiveSliderEnded(double mapTimeMs)
    {
        return ActiveSlider is not null
            && (!ActiveSlider.DurationMs.HasValue || mapTimeMs >= ActiveSlider.TimeMs + ActiveSlider.DurationMs.Value);
    }

    private static double OsuCircleRadius(double cs) => 54.4 - 4.48 * cs;

    private static double Distance(double x1, double y1, double x2, double y2)
        => Math.Sqrt(Math.Pow(x2 - x1, 2) + Math.Pow(y2 - y1, 2));
}
