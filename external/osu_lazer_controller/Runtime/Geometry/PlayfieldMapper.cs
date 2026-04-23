using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Geometry;

public sealed class PlayfieldMapper
{
    private const double OsuWidth = 512.0;
    private const double OsuHeight = 384.0;
    private const double Aspect = OsuWidth / OsuHeight;
    private readonly double _padX;
    private readonly double _padY;

    public PlayfieldMapper(double padX = 0.0, double padY = 0.0)
    {
        _padX = Math.Max(0.0, padX);
        _padY = Math.Max(0.0, padY);
    }

    public PlayfieldBounds Compute(WindowInfo window)
    {
        var rawClientWidth = window.ClientWidth;
        var rawClientHeight = window.ClientHeight;
        var clientWidth = Math.Max(1, (int)Math.Round(rawClientWidth - _padX * 2.0));
        var clientHeight = Math.Max(1, (int)Math.Round(rawClientHeight - _padY * 2.0));

        var playfieldWidth = Math.Min(clientWidth, (int)Math.Round(clientHeight * Aspect));
        var playfieldHeight = Math.Min(clientHeight, (int)Math.Round(playfieldWidth / Aspect));

        var left = window.ClientLeft + (int)Math.Round(_padX) + (clientWidth - playfieldWidth) / 2;
        var top = window.ClientTop + (int)Math.Round(_padY) + (clientHeight - playfieldHeight) / 2;

        return new PlayfieldBounds(left, top, playfieldWidth, playfieldHeight);
    }

    public (double ScreenX, double ScreenY) MapOsuToScreen(PlayfieldBounds bounds, double osuX, double osuY)
    {
        var x = bounds.Left + (osuX / OsuWidth) * bounds.Width;
        var y = bounds.Top + (osuY / OsuHeight) * bounds.Height;
        return (x, y);
    }
}
