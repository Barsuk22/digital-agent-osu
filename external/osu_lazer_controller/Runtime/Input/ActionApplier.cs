using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Input;

public sealed class ActionApplier
{
    private const double MinAdaptiveCompensation = 0.55;
    private const double MaxAdaptiveCompensation = 1.45;
    private const double AdaptiveCompensationAlpha = 0.08;
    private readonly ControlConfig _config;
    private readonly MouseController _mouseController;
    private bool _mouseIsDown;
    private double _smoothedDx;
    private double _smoothedDy;
    private double _adaptiveMovementCompensation = 1.0;

    public ActionApplier(ControlConfig config, MouseController mouseController)
    {
        _config = config;
        _mouseController = mouseController;
    }

    public ActionApplicationResult Apply(
        WindowInfo window,
        ObservationSnapshot snapshot,
        double cursorX,
        double cursorY,
        ActionPacket action)
    {
        var hasImmediateTarget = snapshot.PrimaryObjectKind != "none" || snapshot.ActiveSlider || snapshot.ActiveSpinner;
        var assistedAction = ApplyAimAssist(snapshot, cursorX, cursorY, action, hasImmediateTarget);
        assistedAction = ApplySpinnerOrbitAssist(snapshot, cursorX, cursorY, assistedAction);
        var movementAction = SmoothMovement(assistedAction, hasImmediateTarget, snapshot.ActiveSpinner);
        var effectiveSpeedScale = GetEffectiveSpeedScale(false);
        var nextCursorX = cursorX;
        var nextCursorY = cursorY;
        if (hasImmediateTarget)
        {
            nextCursorX = Clamp(cursorX + movementAction.Dx * effectiveSpeedScale, 0.0, 512.0);
            nextCursorY = Clamp(cursorY + movementAction.Dy * effectiveSpeedScale, 0.0, 384.0);
        }

        var rawClickDown = action.ClickStrength >= _config.ClickThreshold;
        var sliderHoldDown = snapshot.ActiveSlider && action.ClickStrength >= _config.SliderHoldThreshold;
        var spinnerHoldDown = snapshot.ActiveSpinner && action.ClickStrength >= _config.SpinnerHoldThreshold;
        var clickDown = hasImmediateTarget && (rawClickDown || sliderHoldDown || spinnerHoldDown);

        if (_config.EnableMouseMovement)
        {
            _mouseController.MoveToOsu(window, nextCursorX, nextCursorY);
        }

        if (_config.EnableMouseClicks)
        {
            if (clickDown && !_mouseIsDown)
            {
                _mouseController.LeftDown();
                _mouseIsDown = true;
            }
            else if (!clickDown && _mouseIsDown)
            {
                _mouseController.LeftUp();
                _mouseIsDown = false;
            }
        }

        return new ActionApplicationResult(
            NextCursorX: nextCursorX,
            NextCursorY: nextCursorY,
            RawClickDown: rawClickDown,
            SliderHoldDown: sliderHoldDown,
            SpinnerHoldDown: spinnerHoldDown,
            ClickDown: clickDown);
    }

    public void Release()
    {
        if (_mouseIsDown && _config.EnableMouseClicks)
        {
            _mouseController.LeftUp();
        }

        _mouseIsDown = false;
        _smoothedDx = 0.0;
        _smoothedDy = 0.0;
        _adaptiveMovementCompensation = 1.0;
    }

    public void MoveCursor(WindowInfo window, double osuX, double osuY)
    {
        if (_config.EnableMouseMovement)
        {
            _mouseController.MoveToOsu(window, osuX, osuY);
        }
    }

    public void UpdateAdaptiveMovementCompensation(
        bool hasImmediateTarget,
        bool trackedCursorValid,
        double previousCursorX,
        double previousCursorY,
        double commandedCursorX,
        double commandedCursorY,
        double trackedCursorX,
        double trackedCursorY)
    {
        if (!hasImmediateTarget || !trackedCursorValid)
        {
            return;
        }

        var commandedDelta = Distance(previousCursorX, previousCursorY, commandedCursorX, commandedCursorY);
        var trackedDelta = Distance(previousCursorX, previousCursorY, trackedCursorX, trackedCursorY);
        if (commandedDelta < 1.0 || trackedDelta < 0.25)
        {
            return;
        }

        var responseRatio = trackedDelta / commandedDelta;
        var targetCompensation = Clamp(1.0 / Math.Max(0.1, responseRatio), MinAdaptiveCompensation, MaxAdaptiveCompensation);
        _adaptiveMovementCompensation = Lerp(_adaptiveMovementCompensation, targetCompensation, AdaptiveCompensationAlpha);
    }

    private ActionPacket ApplyAimAssist(
        ObservationSnapshot snapshot,
        double cursorX,
        double cursorY,
        ActionPacket action,
        bool hasImmediateTarget)
    {
        if (!hasImmediateTarget || _config.AimAssistStrength <= 0.0 || snapshot.ActiveSpinner)
        {
            return action;
        }

        var targetDxPx = snapshot.AssistTargetX - cursorX;
        var targetDyPx = snapshot.AssistTargetY - cursorY;
        var distancePx = Math.Sqrt((targetDxPx * targetDxPx) + (targetDyPx * targetDyPx));
        if (distancePx <= _config.AimAssistDeadzone)
        {
            return action;
        }

        var maxDistance = Math.Max(_config.AimAssistDeadzone + 1.0, _config.AimAssistMaxDistance);
        var assistWeight = Clamp(
            ((distancePx - _config.AimAssistDeadzone) / (maxDistance - _config.AimAssistDeadzone)) * _config.AimAssistStrength,
            0.0,
            1.0);

        var effectiveSpeedScale = GetEffectiveSpeedScale(false);
        var assistDx = Clamp(targetDxPx / Math.Max(1.0, effectiveSpeedScale), -1.0, 1.0);
        var assistDy = Clamp(targetDyPx / Math.Max(1.0, effectiveSpeedScale), -1.0, 1.0);
        var policyNextX = Clamp(cursorX + action.Dx * effectiveSpeedScale, 0.0, 512.0);
        var policyNextY = Clamp(cursorY + action.Dy * effectiveSpeedScale, 0.0, 384.0);
        var policyDistancePx = Math.Sqrt(
            Math.Pow(snapshot.AssistTargetX - policyNextX, 2) +
            Math.Pow(snapshot.AssistTargetY - policyNextY, 2));
        var edgeMargin = 42.0;
        var nearEdge =
            cursorX <= edgeMargin ||
            cursorX >= 512.0 - edgeMargin ||
            cursorY <= edgeMargin ||
            cursorY >= 384.0 - edgeMargin;
        var movingAwayFromTarget = policyDistancePx > distancePx + 4.0;
        var targetFar = distancePx >= Math.Max(96.0, _config.AimAssistMaxDistance * 0.75);

        if (nearEdge && movingAwayFromTarget)
        {
            assistWeight = Math.Max(assistWeight, 0.95);
        }
        else if (targetFar && movingAwayFromTarget)
        {
            assistWeight = Math.Max(assistWeight, 0.72);
        }

        var blendedDx = Lerp(action.Dx, assistDx, assistWeight);
        var blendedDy = Lerp(action.Dy, assistDy, assistWeight);

        return action with { Dx = blendedDx, Dy = blendedDy };
    }

    private ActionPacket ApplySpinnerOrbitAssist(
        ObservationSnapshot snapshot,
        double cursorX,
        double cursorY,
        ActionPacket action)
    {
        if (!snapshot.ActiveSpinner)
        {
            return action;
        }

        const double centerX = 256.0;
        const double centerY = 192.0;
        const double targetRadius = 76.0;
        var dx = cursorX - centerX;
        var dy = cursorY - centerY;
        var radius = Math.Sqrt((dx * dx) + (dy * dy));
        if (radius < 1.0)
        {
            dx = 1.0;
            dy = 0.0;
            radius = 1.0;
        }

        var nx = dx / radius;
        var ny = dy / radius;
        var tangentX = -ny;
        var tangentY = nx;
        var spinnerSpeedMultiplier = Clamp(_config.SpinnerOrbitSpeedMultiplier, 0.8, 4.0);
        spinnerSpeedMultiplier = Clamp(spinnerSpeedMultiplier * SpinnerUrgencyMultiplier(snapshot), 1.2, 5.5);
        var radiusCorrection = Clamp((targetRadius - radius) * 0.24, -8.0, 8.0);
        var orbitPxPerTick = Clamp(30.0 * spinnerSpeedMultiplier, 24.0, 90.0);
        var orbitDxPx = (tangentX * orbitPxPerTick) + (nx * radiusCorrection);
        var orbitDyPx = (tangentY * orbitPxPerTick) + (ny * radiusCorrection);
        var effectiveSpeedScale = GetEffectiveSpeedScale(false);
        var orbitDx = Clamp(orbitDxPx / Math.Max(1.0, effectiveSpeedScale), -1.0, 1.0);
        var orbitDy = Clamp(orbitDyPx / Math.Max(1.0, effectiveSpeedScale), -1.0, 1.0);
        var policyMagnitude = Math.Sqrt((action.Dx * action.Dx) + (action.Dy * action.Dy));
        var assistWeightBase = policyMagnitude < 0.42 || radius < 42.0 ? 0.92 : 0.64;
        var assistWeight = Clamp(assistWeightBase + ((spinnerSpeedMultiplier - 1.0) * 0.12), 0.55, 0.98);
        var clickStrength = Math.Max(action.ClickStrength, _config.SpinnerHoldThreshold + 0.22);

        return action with
        {
            Dx = Lerp(action.Dx, orbitDx, assistWeight),
            Dy = Lerp(action.Dy, orbitDy, assistWeight),
            ClickStrength = clickStrength,
        };
    }

    private ActionPacket SmoothMovement(ActionPacket action, bool hasImmediateTarget, bool activeSpinner)
    {
        var smoothing = Clamp(_config.ActionSmoothing, 0.0, activeSpinner ? 0.35 : 0.95);
        if (!hasImmediateTarget || smoothing <= 0.0)
        {
            _smoothedDx = action.Dx;
            _smoothedDy = action.Dy;
            return action;
        }

        _smoothedDx = Lerp(action.Dx, _smoothedDx, smoothing);
        _smoothedDy = Lerp(action.Dy, _smoothedDy, smoothing);
        return action with { Dx = _smoothedDx, Dy = _smoothedDy };
    }

    private static double Clamp(double value, double min, double max) => Math.Max(min, Math.Min(max, value));
    private static double Distance(double ax, double ay, double bx, double by)
    {
        var dx = ax - bx;
        var dy = ay - by;
        return Math.Sqrt((dx * dx) + (dy * dy));
    }
    private double GetEffectiveSpeedScale(bool activeSpinner)
    {
        var speedScale = _config.CursorSpeedScale * _adaptiveMovementCompensation;
        if (activeSpinner)
        {
            speedScale *= Clamp(_config.SpinnerOrbitSpeedMultiplier, 0.8, 4.0);
        }

        return speedScale;
    }

    private static double SpinnerUrgencyMultiplier(ObservationSnapshot snapshot)
    {
        if (snapshot.Vector.Length < 59)
        {
            return 1.0;
        }

        var spins = snapshot.Vector[49] * 8.0;
        var targetSpins = snapshot.Vector[50] * 8.0;
        var timeToEndSeconds = Math.Max(0.05, snapshot.Vector[51]);
        var requiredSpinsPerSecond = Math.Max(0.0, targetSpins - spins) / timeToEndSeconds;

        if (requiredSpinsPerSecond >= 3.8)
        {
            return 1.35;
        }

        if (requiredSpinsPerSecond >= 3.1)
        {
            return 1.18;
        }

        if (requiredSpinsPerSecond <= 1.6)
        {
            return 0.88;
        }

        return 1.0;
    }
    private static double Lerp(double start, double end, double amount) => start + ((end - start) * amount);
}

public sealed record ActionApplicationResult(
    double NextCursorX,
    double NextCursorY,
    bool RawClickDown,
    bool SliderHoldDown,
    bool SpinnerHoldDown,
    bool ClickDown);
