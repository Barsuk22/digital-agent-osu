using System.Diagnostics;
using OsuLazerController.Config;
using OsuLazerController.Models;
using OsuLazerController.Runtime.Bridge;
using OsuLazerController.Runtime.Beatmaps;
using OsuLazerController.Runtime.Geometry;
using OsuLazerController.Runtime.Input;
using OsuLazerController.Runtime.Logging;
using OsuLazerController.Runtime.Observations;
using OsuLazerController.Runtime.Timing;

namespace OsuLazerController.Runtime;

public sealed record WarmupResult(bool Ok, double PolicyLatencyMs);

public sealed class ControlLoop
{
    private const double LiveCursorResyncThresholdPx = 18.0;
    private const double LiveCursorCorrectionAlpha = 0.35;
    private const double LiveCursorMaxCorrectionPx = 6.0;
    private readonly RuntimeConfig _config;
    private readonly IPolicyBridge _policyBridge;
    private readonly TraceLogger _traceLogger;
    private readonly ObservationBuilder _observationBuilder = new();
    private readonly ObservationRuntimeState _runtimeState = new();
    private readonly CursorTracker _cursorTracker = new();
    private readonly CursorRuntimeState _cursorRuntimeState = new();
    private readonly PlayfieldMapper _playfieldMapper;
    private readonly ActionApplier _actionApplier;

    public ControlLoop(RuntimeConfig config, IPolicyBridge policyBridge, TraceLogger traceLogger, MouseController mouseController)
    {
        _config = config;
        _policyBridge = policyBridge;
        _traceLogger = traceLogger;
        _playfieldMapper = new PlayfieldMapper(config.Control.PlayfieldPadX, config.Control.PlayfieldPadY);
        _actionApplier = new ActionApplier(config.Control, mouseController);
    }

    public async Task<WarmupResult> RunWarmupAsync(CancellationToken cancellationToken = default)
    {
        var observation = BuildPlaceholderObservation(_config.PolicyBridge.ObservationSize);
        var timer = Stopwatch.StartNew();
        var action = await _policyBridge.RequestActionAsync(observation, cancellationToken);
        timer.Stop();

        _traceLogger.Append(
            new RuntimeTick(
                TickIndex: 0,
                MapTimeMs: 0.0,
                CursorX: 0.0,
                CursorY: 0.0,
                Observation: observation.Obs,
                PrimaryObject: "warmup",
                ActiveSlider: false,
                ActiveSpinner: false,
                AssistTargetX: 0.0,
                AssistTargetY: 0.0,
                LoopElapsedMs: timer.Elapsed.TotalMilliseconds,
                PolicyLatencyMs: timer.Elapsed.TotalMilliseconds,
                Action: action,
                AppliedCursorX: 0.0,
                AppliedCursorY: 0.0,
                TrackedCursorX: 0.0,
                TrackedCursorY: 0.0,
                TrackedCursorValid: false,
                JustPressed: false,
                RawClickDown: false,
                SliderHoldDown: false,
                SpinnerHoldDown: false,
                ClickDown: false));

        return new WarmupResult(true, timer.Elapsed.TotalMilliseconds);
    }

    public async Task RunDiagnosticTicksAsync(
        BridgeBeatmap beatmap,
        WindowInfo window,
        Func<string>? windowTitleProvider = null,
        CancellationToken cancellationToken = default)
    {
        var playfield = _playfieldMapper.Compute(window);
        _runtimeState.Reset();
        InitializeCursor(window, playfield);
        var timer = new MapTimer(_config.Timing);
        await timer.StartAsync(windowTitleProvider, beatmap, cancellationToken);
        double? previousMapTimeMs = null;

        var tickInterval = TimeSpan.FromSeconds(1.0 / Math.Max(1.0, _config.Timing.TickRateHz));

        var unlimitedTicks = _config.Timing.DiagnosticTicks <= 0;
        var maxTicks = unlimitedTicks ? int.MaxValue : Math.Max(1, _config.Timing.DiagnosticTicks);

        for (var tick = 0; tick < maxTicks; tick++)
        {
            cancellationToken.ThrowIfCancellationRequested();

            var tickTimer = Stopwatch.StartNew();
            var mapTimeMs = timer.CurrentTimeMs();
            var dtMs = previousMapTimeMs.HasValue ? Math.Max(1.0, mapTimeMs - previousMapTimeMs.Value) : tickInterval.TotalMilliseconds;
            previousMapTimeMs = mapTimeMs;
            var useLiveCursor = _config.Control.UseLiveCursorTracking;
            var (cursorX, cursorY) = (_cursorRuntimeState.CursorX, _cursorRuntimeState.CursorY);
            if (useLiveCursor && _cursorTracker.TryGetOsuPosition(playfield, out var liveCursorX, out var liveCursorY))
            {
                var liveError = Distance(cursorX, cursorY, liveCursorX, liveCursorY);
                if (liveError >= LiveCursorResyncThresholdPx)
                {
                    cursorX = liveCursorX;
                    cursorY = liveCursorY;
                }
                else
                {
                    (cursorX, cursorY) = ApplyLiveCorrection(cursorX, cursorY, liveCursorX, liveCursorY);
                }
            }
            _runtimeState.Sync(beatmap, mapTimeMs);
            var upcoming = _runtimeState.PeekUpcoming(beatmap, 5);
            var snapshot = _observationBuilder.Build(beatmap, mapTimeMs, cursorX, cursorY, upcoming, _runtimeState);
            var policyTimer = Stopwatch.StartNew();
            var action = await _policyBridge.RequestActionAsync(new ObservationPacket(snapshot.Vector), cancellationToken);
            policyTimer.Stop();
            var primary = snapshot.Upcoming.FirstOrDefault();
            var primaryLabel = primary is null ? "none" : $"{primary.Kind}@{primary.TimeMs:0.0}";
            var applied = _actionApplier.Apply(window, snapshot, cursorX, cursorY, action);
            var trackedCursorValid = _cursorTracker.TryGetOsuPosition(playfield, out var trackedCursorX, out var trackedCursorY);
            var nextCursorX = applied.NextCursorX;
            var nextCursorY = applied.NextCursorY;
            if (useLiveCursor && trackedCursorValid)
            {
                var trackingError = Distance(applied.NextCursorX, applied.NextCursorY, trackedCursorX, trackedCursorY);
                if (trackingError >= LiveCursorResyncThresholdPx)
                {
                    nextCursorX = trackedCursorX;
                    nextCursorY = trackedCursorY;
                }
                else
                {
                    (nextCursorX, nextCursorY) = ApplyLiveCorrection(
                        applied.NextCursorX,
                        applied.NextCursorY,
                        trackedCursorX,
                        trackedCursorY);
                }
            }
            _runtimeState.AdvancePostAction(
                beatmap,
                mapTimeMs,
                nextCursorX,
                nextCursorY,
                applied.RawClickDown,
                applied.ClickDown,
                dtMs);
            _cursorRuntimeState.Set(nextCursorX, nextCursorY);
            tickTimer.Stop();

            _traceLogger.Append(
                new RuntimeTick(
                    TickIndex: tick + 1,
                    MapTimeMs: mapTimeMs,
                    CursorX: cursorX,
                    CursorY: cursorY,
                    Observation: snapshot.Vector,
                    PrimaryObject: primaryLabel,
                    ActiveSlider: snapshot.ActiveSlider,
                    ActiveSpinner: snapshot.ActiveSpinner,
                    AssistTargetX: snapshot.AssistTargetX,
                    AssistTargetY: snapshot.AssistTargetY,
                    LoopElapsedMs: tickTimer.Elapsed.TotalMilliseconds,
                    PolicyLatencyMs: policyTimer.Elapsed.TotalMilliseconds,
                    Action: action,
                    AppliedCursorX: applied.NextCursorX,
                    AppliedCursorY: applied.NextCursorY,
                    TrackedCursorX: trackedCursorX,
                    TrackedCursorY: trackedCursorY,
                    TrackedCursorValid: trackedCursorValid,
                    JustPressed: _runtimeState.JustPressed,
                    RawClickDown: applied.RawClickDown,
                    SliderHoldDown: applied.SliderHoldDown,
                    SpinnerHoldDown: applied.SpinnerHoldDown,
                    ClickDown: applied.ClickDown));

            var trackedLabel = trackedCursorValid
                ? $" tracked=({trackedCursorX:0.0},{trackedCursorY:0.0})"
                : " tracked=(n/a)";
            Console.WriteLine(
                $"[tick {tick + 1:00}] t={mapTimeMs:0.0}ms cursor=({cursorX:0.0},{cursorY:0.0}) " +
                $"primary={primaryLabel} " +
                $"active[s={snapshot.ActiveSlider} sp={snapshot.ActiveSpinner}] " +
                $"action=({action.Dx:0.000},{action.Dy:0.000},{action.ClickStrength:0.000}) " +
                $"applied=({applied.NextCursorX:0.0},{applied.NextCursorY:0.0})" +
                trackedLabel + " " +
                $"hold[j={_runtimeState.JustPressed} r={applied.RawClickDown} sl={applied.SliderHoldDown} sp={applied.SpinnerHoldDown}] " +
                $"move={_config.Control.EnableMouseMovement} click={_config.Control.EnableMouseClicks}");

            var remaining = tickInterval - tickTimer.Elapsed;
            if (remaining > TimeSpan.Zero)
            {
                await Task.Delay(remaining, cancellationToken);
            }

            if (unlimitedTicks && IsPlaybackFinished(beatmap))
            {
                Console.WriteLine($"[timer] playback finished at t={mapTimeMs:0.0}ms tick={tick + 1}");
                break;
            }
        }

        _actionApplier.Release();
    }

    private void InitializeCursor(WindowInfo window, PlayfieldBounds playfield)
    {
        var shouldRecenter = _config.Control.RecenterCursorOnStart
            && (_config.Control.EnableMouseMovement || _config.Control.EnableMouseClicks);

        if (shouldRecenter)
        {
            _actionApplier.Release();
            var targetX = 256.0;
            var targetY = 192.0;

            // Empirically re-center against the tracked cursor because Windows/osu!lazer
            // can land a few pixels away from the nominal absolute mouse target.
            for (var attempt = 0; attempt < 4; attempt++)
            {
                _actionApplier.MoveCursor(window, targetX, targetY);
                Thread.Sleep(24);

                if (!_cursorTracker.TryGetOsuPosition(playfield, out var trackedX, out var trackedY))
                {
                    continue;
                }

                var errorX = trackedX - 256.0;
                var errorY = trackedY - 192.0;
                if (Math.Abs(errorX) <= 2.0 && Math.Abs(errorY) <= 2.0)
                {
                    _cursorRuntimeState.Initialize(256.0, 192.0);
                    return;
                }

                targetX = Math.Clamp(targetX - errorX, 0.0, 512.0);
                targetY = Math.Clamp(targetY - errorY, 0.0, 384.0);
            }

            if (_cursorTracker.TryGetOsuPosition(playfield, out var finalTrackedX, out var finalTrackedY))
            {
                var finalError = Distance(256.0, 192.0, finalTrackedX, finalTrackedY);
                if (finalError >= LiveCursorResyncThresholdPx)
                {
                    _cursorRuntimeState.Initialize(finalTrackedX, finalTrackedY);
                    return;
                }

                _cursorRuntimeState.Initialize(256.0, 192.0);
                return;
            }

            _cursorRuntimeState.Initialize(256.0, 192.0);
            return;
        }

        var (initialCursorX, initialCursorY) = _cursorTracker.GetOsuPosition(playfield);
        _cursorRuntimeState.Initialize(initialCursorX, initialCursorY);
    }

    private static ObservationPacket BuildPlaceholderObservation(int size)
    {
        var obs = new float[size];
        return new ObservationPacket(obs);
    }

    private static double Distance(double ax, double ay, double bx, double by)
    {
        var dx = ax - bx;
        var dy = ay - by;
        return Math.Sqrt((dx * dx) + (dy * dy));
    }

    private static (double X, double Y) ApplyLiveCorrection(double predictedX, double predictedY, double trackedX, double trackedY)
    {
        var dx = trackedX - predictedX;
        var dy = trackedY - predictedY;
        var distance = Math.Sqrt((dx * dx) + (dy * dy));
        if (distance <= double.Epsilon)
        {
            return (predictedX, predictedY);
        }

        var correctionMagnitude = Math.Min(LiveCursorMaxCorrectionPx, distance * LiveCursorCorrectionAlpha);
        var scale = correctionMagnitude / distance;
        return (predictedX + (dx * scale), predictedY + (dy * scale));
    }

    private bool IsPlaybackFinished(BridgeBeatmap beatmap)
    {
        return _runtimeState.ObjectIndex >= beatmap.HitObjects.Count
               && _runtimeState.ActiveSlider is null
               && _runtimeState.ActiveSpinner is null;
    }
}
