using OsuLazerController.Runtime.Win32;

namespace OsuLazerController.Runtime.Windowing;

public sealed class WindowActivator
{
    public void Activate(nint hWnd)
    {
        _ = NativeMethods.ShowWindow(hWnd, NativeMethods.SW_RESTORE);
        _ = NativeMethods.SetForegroundWindow(hWnd);
    }
}
