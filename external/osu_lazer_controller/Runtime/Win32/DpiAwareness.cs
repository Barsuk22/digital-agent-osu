namespace OsuLazerController.Runtime.Win32;

public static class DpiAwareness
{
    public static void Enable()
    {
        try
        {
            if (NativeMethods.SetProcessDpiAwarenessContext(NativeMethods.DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
            {
                return;
            }
        }
        catch
        {
            // Fall back below on older Windows builds or restricted processes.
        }

        try
        {
            _ = NativeMethods.SetProcessDPIAware();
        }
        catch
        {
            // DPI awareness is best-effort; controller startup should continue.
        }
    }
}
