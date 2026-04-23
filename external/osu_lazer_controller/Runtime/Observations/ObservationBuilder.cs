using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Observations;

public sealed class ObservationBuilder
{
    private const int UpcomingCount = 5;
    private const double SpinnerCenterX = 256.0;
    private const double SpinnerCenterY = 192.0;
    private const double SpinnerTargetRadius = 76.0;
    private const double SpinnerTargetSpins = 2.0;

    public ObservationSnapshot Build(
        BridgeBeatmap beatmap,
        double mapTimeMs,
        double cursorX,
        double cursorY,
        IReadOnlyList<BridgeHitObject> upcoming,
        ObservationRuntimeState runtimeState)
    {
        var values = new List<float>
        {
            (float)(mapTimeMs / 10000.0),
            (float)(cursorX / 512.0),
            (float)(cursorY / 384.0),
        };

        foreach (var obj in upcoming.Take(UpcomingCount))
        {
            var distance = Math.Sqrt(Math.Pow(obj.X - cursorX, 2) + Math.Pow(obj.Y - cursorY, 2));
            values.Add(KindId(obj.Kind));
            values.Add((float)(obj.X / 512.0));
            values.Add((float)(obj.Y / 384.0));
            values.Add((float)((obj.TimeMs - mapTimeMs) / 1000.0));
            values.Add((float)(distance / 512.0));
            values.Add(IsActive(obj, mapTimeMs) ? 1.0f : 0.0f);
        }

        while ((values.Count - 3) / 6 < UpcomingCount)
        {
            values.AddRange([-1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f]);
        }

        var primaryIsSlider = upcoming.FirstOrDefault()?.Kind == "slider" ? 1.0f : 0.0f;
        var primaryIsSpinner = upcoming.FirstOrDefault()?.Kind == "spinner" ? 1.0f : 0.0f;
        var sliderState = BuildSliderState(beatmap, mapTimeMs, cursorX, cursorY, runtimeState);
        var spinnerState = BuildSpinnerState(mapTimeMs, cursorX, cursorY, runtimeState);

        values.AddRange(
        [
            sliderState.ActiveSlider,
            primaryIsSlider,
            sliderState.Progress,
            sliderState.TargetX,
            sliderState.TargetY,
            sliderState.DistanceToTarget,
            sliderState.DistanceToBall,
            sliderState.InsideFollow,
            sliderState.HeadHit,
            sliderState.TimeToEndMs,
            sliderState.TangentX,
            sliderState.TangentY,
            sliderState.FollowRadius,
        ]);

        values.AddRange(
        [
            spinnerState.ActiveSpinner,
            primaryIsSpinner,
            spinnerState.Progress,
            spinnerState.Spins,
            spinnerState.TargetSpins,
            spinnerState.TimeToEndMs,
            spinnerState.CenterX,
            spinnerState.CenterY,
            spinnerState.DistanceToCenter,
            spinnerState.RadiusError,
            spinnerState.AngleSin,
            spinnerState.AngleCos,
            spinnerState.AngularVelocity,
        ]);

        if (values.Count != 59)
        {
            throw new InvalidOperationException($"Observation vector size mismatch: expected 59, got {values.Count}");
        }

        return new ObservationSnapshot(
            MapTimeMs: mapTimeMs,
            CursorX: cursorX,
            CursorY: cursorY,
            Vector: values.ToArray(),
            Upcoming: upcoming,
            ActiveSlider: sliderState.ActiveSlider > 0.5f,
            ActiveSpinner: spinnerState.ActiveSpinner > 0.5f,
            PrimaryObjectKind: upcoming.FirstOrDefault()?.Kind ?? "none",
            AssistTargetX: ResolveAssistTargetX(upcoming, sliderState, spinnerState, cursorX),
            AssistTargetY: ResolveAssistTargetY(upcoming, sliderState, spinnerState, cursorY));
    }

    private static double ResolveAssistTargetX(
        IReadOnlyList<BridgeHitObject> upcoming,
        SliderSnapshot sliderState,
        SpinnerSnapshot spinnerState,
        double cursorX)
    {
        if (spinnerState.ActiveSpinner > 0.5f)
        {
            return SpinnerCenterX;
        }

        if (sliderState.ActiveSlider > 0.5f)
        {
            return sliderState.TargetX * 512.0;
        }

        return upcoming.FirstOrDefault()?.X ?? cursorX;
    }

    private static double ResolveAssistTargetY(
        IReadOnlyList<BridgeHitObject> upcoming,
        SliderSnapshot sliderState,
        SpinnerSnapshot spinnerState,
        double cursorY)
    {
        if (spinnerState.ActiveSpinner > 0.5f)
        {
            return SpinnerCenterY;
        }

        if (sliderState.ActiveSlider > 0.5f)
        {
            return sliderState.TargetY * 384.0;
        }

        return upcoming.FirstOrDefault()?.Y ?? cursorY;
    }

    private SliderSnapshot BuildSliderState(
        BridgeBeatmap beatmap,
        double mapTimeMs,
        double cursorX,
        double cursorY,
        ObservationRuntimeState runtimeState)
    {
        var radius = OsuCircleRadius(beatmap.Difficulty.Cs) * 1.65;
        var slider = runtimeState.ActiveSlider;
        if (slider is null
            || slider.SampledPath is null
            || slider.CumulativeLengths is null
            || !slider.TotalLength.HasValue
            || !slider.Repeats.HasValue
            || !slider.DurationMs.HasValue)
        {
            return SliderSnapshot.Inactive(radius);
        }

        var endTimeMs = slider.TimeMs + slider.DurationMs.Value;
        var progress = Clamp01((mapTimeMs - slider.TimeMs) / Math.Max(1.0, slider.DurationMs.Value));
        var (localProgress, spanIndex) = LocalSliderProgress(progress, slider.Repeats.Value);
        var target = PositionAtProgress(slider, localProgress);
        var tangent = TangentAtProgress(slider, localProgress);
        if (spanIndex % 2 == 1)
        {
            tangent = new BridgePoint(-tangent.X, -tangent.Y);
        }

        var distance = Distance(cursorX, cursorY, target.X, target.Y);

        return new SliderSnapshot(
            ActiveSlider: 1.0f,
            Progress: (float)progress,
            TargetX: (float)(target.X / 512.0),
            TargetY: (float)(target.Y / 384.0),
            DistanceToTarget: (float)(distance / 512.0),
            DistanceToBall: (float)(distance / 512.0),
            InsideFollow: distance <= radius ? 1.0f : 0.0f,
            HeadHit: runtimeState.ActiveSliderHeadHit ? 1.0f : 0.0f,
            TimeToEndMs: (float)(Math.Max(0.0, endTimeMs - mapTimeMs) / 1000.0),
            TangentX: (float)tangent.X,
            TangentY: (float)tangent.Y,
            FollowRadius: (float)(radius / 512.0));
    }

    private SpinnerSnapshot BuildSpinnerState(
        double mapTimeMs,
        double cursorX,
        double cursorY,
        ObservationRuntimeState runtimeState)
    {
        var spinner = runtimeState.ActiveSpinner;
        if (spinner is null || !spinner.EndTimeMs.HasValue || mapTimeMs > spinner.EndTimeMs.Value + 220.0)
        {
            return SpinnerSnapshot.Inactive(cursorX, cursorY);
        }

        var angle = Math.Atan2(cursorY - SpinnerCenterY, cursorX - SpinnerCenterX);
        var distanceToCenter = Distance(cursorX, cursorY, SpinnerCenterX, SpinnerCenterY);
        var radiusError = Math.Abs(distanceToCenter - SpinnerTargetRadius);
        var durationMs = Math.Max(1.0, spinner.EndTimeMs.Value - spinner.TimeMs);
        var progress = Clamp01((mapTimeMs - spinner.TimeMs) / durationMs);
        return new SpinnerSnapshot(
            ActiveSpinner: 1.0f,
            Progress: (float)progress,
            Spins: (float)((runtimeState.SpinnerSpinProgress / (2.0 * Math.PI)) / 8.0),
            TargetSpins: (float)(runtimeState.SpinnerTargetSpinsValue / 8.0),
            TimeToEndMs: (float)(Math.Max(0.0, spinner.EndTimeMs.Value - mapTimeMs) / 1000.0),
            CenterX: (float)(SpinnerCenterX / 512.0),
            CenterY: (float)(SpinnerCenterY / 384.0),
            DistanceToCenter: (float)(distanceToCenter / 256.0),
            RadiusError: (float)(radiusError / 256.0),
            AngleSin: (float)Math.Sin(angle),
            AngleCos: (float)Math.Cos(angle),
            AngularVelocity: (float)(runtimeState.LastAngularVelocity / 60.0));
    }

    private static float KindId(string kind) => kind switch
    {
        "circle" => 0.0f,
        "slider" => 1.0f,
        "spinner" => 2.0f,
        _ => -1.0f,
    };

    private static bool IsActive(BridgeHitObject obj, double mapTimeMs)
    {
        return obj.Kind switch
        {
            "circle" => Math.Abs(obj.TimeMs - mapTimeMs) <= 80.0,
            "slider" => mapTimeMs >= obj.TimeMs,
            "spinner" => mapTimeMs >= obj.TimeMs,
            _ => false,
        };
    }

    private static double OsuCircleRadius(double cs) => 54.4 - 4.48 * cs;

    private static double Clamp01(double value) => Math.Max(0.0, Math.Min(1.0, value));

    private static double Distance(double x1, double y1, double x2, double y2)
        => Math.Sqrt(Math.Pow(x2 - x1, 2) + Math.Pow(y2 - y1, 2));

    private static (double LocalProgress, int SpanIndex) LocalSliderProgress(double progress, int repeats)
    {
        if (repeats <= 0)
        {
            return (0.0, 0);
        }

        var totalProgress = Clamp01(progress);
        var spanProgress = totalProgress * repeats;
        var spanIndex = Math.Min(repeats - 1, (int)spanProgress);
        var localProgress = spanProgress - spanIndex;
        if (spanIndex % 2 == 1)
        {
            localProgress = 1.0 - localProgress;
        }

        return (localProgress, spanIndex);
    }

    private static BridgePoint PositionAtProgress(BridgeHitObject slider, double progress)
    {
        var distanceValue = Clamp01(progress) * slider.TotalLength!.Value;
        return PositionAtDistance(slider, distanceValue);
    }

    private static BridgePoint PositionAtDistance(BridgeHitObject slider, double distanceValue)
    {
        var points = slider.SampledPath!;
        var cumulative = slider.CumulativeLengths!;
        var totalLength = slider.TotalLength!.Value;
        if (points.Count == 0)
        {
            return new BridgePoint(slider.X, slider.Y);
        }

        if (totalLength <= 1e-6)
        {
            return points[0];
        }

        var d = Math.Max(0.0, Math.Min(totalLength, distanceValue));
        for (var i = 1; i < cumulative.Count; i++)
        {
            var prev = cumulative[i - 1];
            var curr = cumulative[i];
            if (d > curr)
            {
                continue;
            }

            var segLen = curr - prev;
            if (segLen <= 1e-9)
            {
                return points[i];
            }

            var t = (d - prev) / segLen;
            var a = points[i - 1];
            var b = points[i];
            return new BridgePoint(
                a.X + (b.X - a.X) * t,
                a.Y + (b.Y - a.Y) * t);
        }

        return points[^1];
    }

    private static BridgePoint TangentAtProgress(BridgeHitObject slider, double progress)
    {
        var totalLength = slider.TotalLength!.Value;
        if (totalLength <= 1e-6)
        {
            return new BridgePoint(0.0, 0.0);
        }

        var centerDistance = Clamp01(progress) * totalLength;
        var a = PositionAtDistance(slider, Math.Max(0.0, centerDistance - 8.0));
        var b = PositionAtDistance(slider, Math.Min(totalLength, centerDistance + 8.0));
        var dx = b.X - a.X;
        var dy = b.Y - a.Y;
        var norm = Math.Sqrt(dx * dx + dy * dy);
        if (norm <= 1e-6)
        {
            return new BridgePoint(0.0, 0.0);
        }

        return new BridgePoint(dx / norm, dy / norm);
    }

    private sealed record SliderSnapshot(
        float ActiveSlider,
        float Progress,
        float TargetX,
        float TargetY,
        float DistanceToTarget,
        float DistanceToBall,
        float InsideFollow,
        float HeadHit,
        float TimeToEndMs,
        float TangentX,
        float TangentY,
        float FollowRadius)
    {
        public static SliderSnapshot Inactive(double radius) => new(0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, (float)(radius / 512.0));
    }

    private sealed record SpinnerSnapshot(
        float ActiveSpinner,
        float Progress,
        float Spins,
        float TargetSpins,
        float TimeToEndMs,
        float CenterX,
        float CenterY,
        float DistanceToCenter,
        float RadiusError,
        float AngleSin,
        float AngleCos,
        float AngularVelocity)
    {
        public static SpinnerSnapshot Inactive(double cursorX, double cursorY)
        {
            var dx = cursorX - SpinnerCenterX;
            var dy = cursorY - SpinnerCenterY;
            var dist = Math.Sqrt(dx * dx + dy * dy);
            var angle = dist > 1e-6 ? Math.Atan2(dy, dx) : 0.0;
            return new SpinnerSnapshot(
                0.0f,
                0.0f,
                0.0f,
                (float)(SpinnerTargetSpins / 8.0),
                0.0f,
                (float)(SpinnerCenterX / 512.0),
                (float)(SpinnerCenterY / 384.0),
                (float)(dist / 256.0),
                (float)(Math.Abs(dist - SpinnerTargetRadius) / 256.0),
                (float)Math.Sin(angle),
                (float)Math.Cos(angle),
                0.0f);
        }
    }
}
