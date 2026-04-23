namespace OsuLazerController.Runtime.Input;

public sealed class CursorRuntimeState
{
    public double CursorX { get; private set; }
    public double CursorY { get; private set; }
    public bool Initialized { get; private set; }

    public void Initialize(double cursorX, double cursorY)
    {
        CursorX = Clamp(cursorX, 0.0, 512.0);
        CursorY = Clamp(cursorY, 0.0, 384.0);
        Initialized = true;
    }

    public void Set(double cursorX, double cursorY)
    {
        CursorX = Clamp(cursorX, 0.0, 512.0);
        CursorY = Clamp(cursorY, 0.0, 384.0);
    }

    private static double Clamp(double value, double min, double max) => Math.Max(min, Math.Min(max, value));
}
