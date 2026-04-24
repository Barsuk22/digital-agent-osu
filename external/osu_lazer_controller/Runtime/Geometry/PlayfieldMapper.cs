using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Geometry;

public sealed class PlayfieldMapper
{
    private const double OsuWidth = 512.0;
    private const double OsuHeight = 384.0;
    private const double Aspect = OsuWidth / OsuHeight;
    private readonly double _padX;
    private readonly double _padY;
    private readonly double _scaleX;
    private readonly double _scaleY;
    private readonly double _offsetX;
    private readonly double _offsetY;

    public PlayfieldMapper(
        double padX = 0.0,
        double padY = 0.0,
        double scaleX = 1.0,
        double scaleY = 1.0,
        double offsetX = 0.0,
        double offsetY = 0.0)
    {
        _padX = Math.Max(0.0, padX);
        _padY = Math.Max(0.0, padY);
        _scaleX = scaleX > 0.0 ? scaleX : 1.0;
        _scaleY = scaleY > 0.0 ? scaleY : 1.0;
        _offsetX = offsetX;
        _offsetY = offsetY;
    }

    public PlayfieldBounds Compute(WindowInfo window)
    {
        var rawClientWidth = window.ClientWidth;
        var rawClientHeight = window.ClientHeight;
        var clientWidth = Math.Max(1, (int)Math.Round(rawClientWidth - _padX * 2.0));
        var clientHeight = Math.Max(1, (int)Math.Round(rawClientHeight - _padY * 2.0));

        var playfieldWidth = Math.Min(clientWidth, (int)Math.Round(clientHeight * Aspect));
        var playfieldHeight = Math.Min(clientHeight, (int)Math.Round(playfieldWidth / Aspect));

        playfieldWidth = Math.Max(1, (int)Math.Round(playfieldWidth * _scaleX));
        playfieldHeight = Math.Max(1, (int)Math.Round(playfieldHeight * _scaleY));

        var left = window.ClientLeft + (int)Math.Round(_padX) + (clientWidth - playfieldWidth) / 2 + (int)Math.Round(_offsetX);
        var top = window.ClientTop + (int)Math.Round(_padY) + (clientHeight - playfieldHeight) / 2 + (int)Math.Round(_offsetY);

        return new PlayfieldBounds(left, top, playfieldWidth, playfieldHeight);
    }

    public (double ScreenX, double ScreenY) MapOsuToScreen(PlayfieldBounds bounds, double osuX, double osuY)
    {
        var x = bounds.Left + (osuX / OsuWidth) * bounds.Width;
        var y = bounds.Top + (osuY / OsuHeight) * bounds.Height;
        return (x, y);
    }
}
