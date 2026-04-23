namespace OsuLazerController.Models;

public sealed record PlayfieldBounds(
    int Left,
    int Top,
    int Width,
    int Height)
{
    public double Right => Left + Width;
    public double Bottom => Top + Height;
}
