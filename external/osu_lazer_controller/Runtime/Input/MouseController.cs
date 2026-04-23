using System.Runtime.InteropServices;
using OsuLazerController.Models;
using OsuLazerController.Runtime.Geometry;
using OsuLazerController.Runtime.Win32;

namespace OsuLazerController.Runtime.Input;

public sealed class MouseController
{
    private readonly PlayfieldMapper _playfieldMapper;

    public MouseController(double playfieldPadX = 0.0, double playfieldPadY = 0.0)
    {
        _playfieldMapper = new PlayfieldMapper(playfieldPadX, playfieldPadY);
    }

    public void MoveToScreen(double x, double y)
    {
        var virtualLeft = NativeMethods.GetSystemMetrics(NativeMethods.SM_XVIRTUALSCREEN);
        var virtualTop = NativeMethods.GetSystemMetrics(NativeMethods.SM_YVIRTUALSCREEN);
        var virtualWidth = Math.Max(1, NativeMethods.GetSystemMetrics(NativeMethods.SM_CXVIRTUALSCREEN));
        var virtualHeight = Math.Max(1, NativeMethods.GetSystemMetrics(NativeMethods.SM_CYVIRTUALSCREEN));

        var clampedScreenX = Math.Clamp(x, virtualLeft, virtualLeft + virtualWidth - 1);
        var clampedScreenY = Math.Clamp(y, virtualTop, virtualTop + virtualHeight - 1);
        var normalizedX = NormalizeAbsoluteCoordinate(clampedScreenX, virtualLeft, virtualWidth);
        var normalizedY = NormalizeAbsoluteCoordinate(clampedScreenY, virtualTop, virtualHeight);

        var input = new NativeMethods.INPUT
        {
            Type = NativeMethods.INPUT_MOUSE,
            Data = new NativeMethods.InputUnion
            {
                Mouse = new NativeMethods.MOUSEINPUT
                {
                    Dx = normalizedX,
                    Dy = normalizedY,
                    DwFlags = NativeMethods.MOUSEEVENTF_MOVE | NativeMethods.MOUSEEVENTF_ABSOLUTE | NativeMethods.MOUSEEVENTF_VIRTUALDESK,
                },
            },
        };

        NativeMethods.SendInput(1, [input], Marshal.SizeOf<NativeMethods.INPUT>());
    }

    public void MoveToOsu(WindowInfo window, double osuX, double osuY)
    {
        var bounds = _playfieldMapper.Compute(window);
        var (screenX, screenY) = _playfieldMapper.MapOsuToScreen(bounds, osuX, osuY);
        MoveToScreen(screenX, screenY);
    }

    public void LeftDown() => SendMouseButton(NativeMethods.MOUSEEVENTF_LEFTDOWN);

    public void LeftUp() => SendMouseButton(NativeMethods.MOUSEEVENTF_LEFTUP);

    private static void SendMouseButton(uint flags)
    {
        var input = new NativeMethods.INPUT
        {
            Type = NativeMethods.INPUT_MOUSE,
            Data = new NativeMethods.InputUnion
            {
                Mouse = new NativeMethods.MOUSEINPUT
                {
                    DwFlags = flags,
                },
            },
        };

        NativeMethods.SendInput(1, [input], Marshal.SizeOf<NativeMethods.INPUT>());
    }

    private static int NormalizeAbsoluteCoordinate(double value, int virtualOrigin, int virtualSize)
    {
        if (virtualSize <= 1)
        {
            return 0;
        }

        return (int)Math.Round((value - virtualOrigin) * 65535.0 / (virtualSize - 1));
    }
}
