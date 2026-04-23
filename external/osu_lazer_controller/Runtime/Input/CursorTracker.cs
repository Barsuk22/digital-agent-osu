using System.Runtime.InteropServices;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Input;

public sealed class CursorTracker
{
    public (double ScreenX, double ScreenY) GetScreenPosition()
    {
        if (!GetCursorPos(out var point))
        {
            return (0.0, 0.0);
        }

        return (point.X, point.Y);
    }

    public bool TryGetOsuPosition(PlayfieldBounds bounds, out double osuX, out double osuY, double marginPx = 48.0)
    {
        var (screenX, screenY) = GetScreenPosition();
        if (screenX < bounds.Left - marginPx
            || screenX > bounds.Left + bounds.Width + marginPx
            || screenY < bounds.Top - marginPx
            || screenY > bounds.Top + bounds.Height + marginPx)
        {
            osuX = 0.0;
            osuY = 0.0;
            return false;
        }

        var relX = (screenX - bounds.Left) / Math.Max(1.0, bounds.Width);
        var relY = (screenY - bounds.Top) / Math.Max(1.0, bounds.Height);
        osuX = Clamp(relX, 0.0, 1.0) * 512.0;
        osuY = Clamp(relY, 0.0, 1.0) * 384.0;
        return true;
    }

    public (double OsuX, double OsuY) GetOsuPosition(PlayfieldBounds bounds)
    {
        if (TryGetOsuPosition(bounds, out var osuX, out var osuY))
        {
            return (osuX, osuY);
        }

        return (0.0, 0.0);
    }

    private static double Clamp(double value, double min, double max) => Math.Max(min, Math.Min(max, value));

    [DllImport("user32.dll")]
    private static extern bool GetCursorPos(out POINT lpPoint);

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT
    {
        public int X;
        public int Y;
    }
}
