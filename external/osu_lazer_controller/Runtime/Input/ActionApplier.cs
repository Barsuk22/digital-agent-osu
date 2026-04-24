using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Input;

public sealed class ActionApplier
{
    private readonly ControlConfig _config;
    private readonly MouseController _mouseController;
    private bool _mouseIsDown;
    private double _smoothedDx;
    private double _smoothedDy;

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
        var nextCursorX = cursorX;
        var nextCursorY = cursorY;
        if (hasImmediateTarget)
        {
            nextCursorX = Clamp(cursorX + movementAction.Dx * _config.CursorSpeedScale, 0.0, 512.0);
            nextCursorY = Clamp(cursorY + movementAction.Dy * _config.CursorSpeedScale, 0.0, 384.0);
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
    }

    public void MoveCursor(WindowInfo window, double osuX, double osuY)
    {
        if (_config.EnableMouseMovement)
        {
            _mouseController.MoveToOsu(window, osuX, osuY);
        }
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

        var assistDx = Clamp(targetDxPx / Math.Max(1.0, _config.CursorSpeedScale), -1.0, 1.0);
        var assistDy = Clamp(targetDyPx / Math.Max(1.0, _config.CursorSpeedScale), -1.0, 1.0);
        var policyNextX = Clamp(cursorX + action.Dx * _config.CursorSpeedScale, 0.0, 512.0);
        var policyNextY = Clamp(cursorY + action.Dy * _config.CursorSpeedScale, 0.0, 384.0);
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
        var radiusCorrection = Clamp((targetRadius - radius) * 0.18, -5.0, 5.0);
        var orbitDxPx = (tangentX * 11.5) + (nx * radiusCorrection);
        var orbitDyPx = (tangentY * 11.5) + (ny * radiusCorrection);
        var orbitDx = Clamp(orbitDxPx / Math.Max(1.0, _config.CursorSpeedScale), -1.0, 1.0);
        var orbitDy = Clamp(orbitDyPx / Math.Max(1.0, _config.CursorSpeedScale), -1.0, 1.0);
        var policyMagnitude = Math.Sqrt((action.Dx * action.Dx) + (action.Dy * action.Dy));
        var assistWeight = policyMagnitude < 0.28 || radius < 42.0 ? 0.78 : 0.36;
        var clickStrength = Math.Max(action.ClickStrength, _config.SpinnerHoldThreshold + 0.12);

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
    private static double Lerp(double start, double end, double amount) => start + ((end - start) * amount);
}

public sealed record ActionApplicationResult(
    double NextCursorX,
    double NextCursorY,
    bool RawClickDown,
    bool SliderHoldDown,
    bool SpinnerHoldDown,
    bool ClickDown);
