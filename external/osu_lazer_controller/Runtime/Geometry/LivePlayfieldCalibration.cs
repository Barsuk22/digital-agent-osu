using System.Runtime.InteropServices;
using OsuLazerController.Config;

namespace OsuLazerController.Runtime.Geometry;

public static class LivePlayfieldCalibration
{
    private static double _scaleX = 1.0;
    private static double _scaleY = 1.0;
    private static double _offsetX;
    private static double _offsetY;
    private static bool _leftWasDown;
    private static bool _rightWasDown;
    private static bool _upWasDown;
    private static bool _downWasDown;
    private static bool _f1WasDown;
    private static bool _f2WasDown;
    private static bool _f3WasDown;
    private static bool _f4WasDown;
    private static bool _f5WasDown;

    public static void Initialize(ControlConfig config)
    {
        _scaleX = config.PlayfieldScaleX > 0.0 ? config.PlayfieldScaleX : 1.0;
        _scaleY = config.PlayfieldScaleY > 0.0 ? config.PlayfieldScaleY : 1.0;
        _offsetX = config.PlayfieldOffsetX;
        _offsetY = config.PlayfieldOffsetY;
    }

    public static (double ScaleX, double ScaleY, double OffsetX, double OffsetY) Current()
        => (_scaleX, _scaleY, _offsetX, _offsetY);

    public static void PrintHelp()
    {
        Console.WriteLine("[playfield] live keys: arrows=offset +/-5px, F1/F2=scaleY -/+, F3/F4=scaleX -/+, F5=print");
    }

    public static void PollHotkeys()
    {
        ApplyOffsetOnPress(0x25, ref _leftWasDown, -5.0, 0.0);
        ApplyOffsetOnPress(0x27, ref _rightWasDown, 5.0, 0.0);
        ApplyOffsetOnPress(0x26, ref _upWasDown, 0.0, -5.0);
        ApplyOffsetOnPress(0x28, ref _downWasDown, 0.0, 5.0);
        ApplyScaleOnPress(0x70, ref _f1WasDown, 0.0, -0.01);
        ApplyScaleOnPress(0x71, ref _f2WasDown, 0.0, 0.01);
        ApplyScaleOnPress(0x72, ref _f3WasDown, -0.01, 0.0);
        ApplyScaleOnPress(0x73, ref _f4WasDown, 0.01, 0.0);

        var f5Down = IsKeyDown(0x74);
        if (f5Down && !_f5WasDown)
        {
            PrintCurrent();
        }

        _f5WasDown = f5Down;
    }

    private static void ApplyOffsetOnPress(int virtualKey, ref bool wasDown, double dx, double dy)
    {
        var isDown = IsKeyDown(virtualKey);
        if (isDown && !wasDown)
        {
            _offsetX += dx;
            _offsetY += dy;
            PrintCurrent();
        }

        wasDown = isDown;
    }

    private static void ApplyScaleOnPress(int virtualKey, ref bool wasDown, double dx, double dy)
    {
        var isDown = IsKeyDown(virtualKey);
        if (isDown && !wasDown)
        {
            _scaleX = Math.Max(0.50, _scaleX + dx);
            _scaleY = Math.Max(0.50, _scaleY + dy);
            PrintCurrent();
        }

        wasDown = isDown;
    }

    private static void PrintCurrent()
    {
        Console.WriteLine(
            $"[playfield] scale=({_scaleX:0.###},{_scaleY:0.###}) offset=({_offsetX:+0;-0;0},{_offsetY:+0;-0;0})");
    }

    private static bool IsKeyDown(int virtualKey) => (GetAsyncKeyState(virtualKey) & 0x8000) != 0;

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int vKey);
}
