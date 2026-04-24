using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Input;

public sealed class OracleActionPlanner
{
    private const double SpinnerCenterX = 256.0;
    private const double SpinnerCenterY = 192.0;
    private const double SpinnerRadius = 76.0;
    private const double SpinnerAngularSpeedRadPerSecond = 14.0;
    private const double ClickEarlyMs = 18.0;
    private const double ClickLateMs = 92.0;
    private readonly ControlConfig _controlConfig;

    public OracleActionPlanner(ControlConfig controlConfig)
    {
        _controlConfig = controlConfig;
    }

    public ActionPacket Plan(BridgeBeatmap beatmap, ObservationSnapshot snapshot)
    {
        if (snapshot.ActiveSpinner)
        {
            var angle = Math.Atan2(snapshot.CursorY - SpinnerCenterY, snapshot.CursorX - SpinnerCenterX);
            var spinnerDistance = Distance(snapshot.CursorX, snapshot.CursorY, SpinnerCenterX, SpinnerCenterY);
            if (spinnerDistance < 24.0)
            {
                angle = snapshot.MapTimeMs / 1000.0 * SpinnerAngularSpeedRadPerSecond;
            }

            var targetAngle = angle + SpinnerAngularSpeedRadPerSecond / Math.Max(1.0, 60.0);
            return MoveToward(
                SpinnerCenterX + Math.Cos(targetAngle) * SpinnerRadius,
                SpinnerCenterY + Math.Sin(targetAngle) * SpinnerRadius,
                snapshot.CursorX,
                snapshot.CursorY,
                clickStrength: 1.0);
        }

        if (snapshot.ActiveSlider)
        {
            return MoveToward(snapshot.AssistTargetX, snapshot.AssistTargetY, snapshot.CursorX, snapshot.CursorY, 1.0);
        }

        var primary = snapshot.Upcoming.FirstOrDefault();
        if (primary is null)
        {
            return new ActionPacket(0.0, 0.0, 0.0);
        }

        var timeToPrimaryMs = primary.TimeMs - snapshot.MapTimeMs;
        var radius = OsuCircleRadius(beatmap.Difficulty.Cs);
        var distance = Distance(snapshot.CursorX, snapshot.CursorY, primary.X, primary.Y);
        var shouldClick = timeToPrimaryMs <= ClickEarlyMs
                          && timeToPrimaryMs >= -ClickLateMs
                          && distance <= radius * 1.25;

        if (primary.Kind == "spinner" && primary.EndTimeMs.HasValue && snapshot.MapTimeMs >= primary.TimeMs - 25.0)
        {
            return MoveToward(
                SpinnerCenterX + SpinnerRadius,
                SpinnerCenterY,
                snapshot.CursorX,
                snapshot.CursorY,
                clickStrength: 1.0);
        }

        return MoveToward(primary.X, primary.Y, snapshot.CursorX, snapshot.CursorY, shouldClick ? 1.0 : 0.0);
    }

    private ActionPacket MoveToward(double targetX, double targetY, double cursorX, double cursorY, double clickStrength)
    {
        var speed = Math.Max(1.0, _controlConfig.CursorSpeedScale);
        return new ActionPacket(
            Dx: Clamp((targetX - cursorX) / speed, -1.0, 1.0),
            Dy: Clamp((targetY - cursorY) / speed, -1.0, 1.0),
            ClickStrength: clickStrength);
    }

    private static double OsuCircleRadius(double cs) => 54.4 - 4.48 * cs;

    private static double Distance(double x1, double y1, double x2, double y2)
        => Math.Sqrt(Math.Pow(x2 - x1, 2) + Math.Pow(y2 - y1, 2));

    private static double Clamp(double value, double min, double max) => Math.Max(min, Math.Min(max, value));
}
