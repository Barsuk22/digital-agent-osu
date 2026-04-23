using System.Diagnostics;
using System.Text;
using OsuLazerController.Config;
using OsuLazerController.Models;
using OsuLazerController.Runtime.Win32;

namespace OsuLazerController.Runtime.Windowing;

public sealed class WindowLocator
{
    private readonly WindowConfig _config;

    public WindowLocator(WindowConfig config)
    {
        _config = config;
    }

    public WindowInfo? FindGameWindow()
    {
        var targetProcesses = Process
            .GetProcesses()
            .Where(p =>
            {
                try
                {
                    return MatchesHint(p.ProcessName, _config.ProcessName);
                }
                catch
                {
                    return false;
                }
            })
            .ToDictionary(p => p.Id);

        WindowInfo? best = null;

        NativeMethods.EnumWindows((hWnd, _) =>
        {
            if (!NativeMethods.IsWindowVisible(hWnd))
            {
                return true;
            }

            NativeMethods.GetWindowThreadProcessId(hWnd, out var processIdRaw);
            var processId = unchecked((int)processIdRaw);

            if (!targetProcesses.TryGetValue(processId, out var process))
            {
                return true;
            }

            var candidate = BuildWindowInfo(process, hWnd);
            if (candidate is not null && (best is null || candidate.ClientWidth * candidate.ClientHeight > best.ClientWidth * best.ClientHeight))
            {
                best = candidate;
            }

            return true;
        }, nint.Zero);

        if (best is not null)
        {
            return best;
        }

        foreach (var process in targetProcesses.Values)
        {
            try
            {
                if (process.MainWindowHandle == nint.Zero)
                {
                    continue;
                }

                var candidate = BuildWindowInfo(process, process.MainWindowHandle);
                if (candidate is not null && (best is null || candidate.ClientWidth * candidate.ClientHeight > best.ClientWidth * best.ClientHeight))
                {
                    best = candidate;
                }
            }
            catch
            {
                // Ignore transient processes during startup/shutdown.
            }
        }

        return best;
    }

    private WindowInfo? BuildWindowInfo(Process process, nint hWnd)
    {
        var title = GetWindowTitle(hWnd);
        if (!string.IsNullOrWhiteSpace(_config.TitleHint) &&
            !MatchesHint(title, _config.TitleHint))
        {
            if (!string.IsNullOrWhiteSpace(title))
            {
                return null;
            }
        }

        if (!NativeMethods.GetWindowRect(hWnd, out var windowRect))
        {
            return null;
        }

        if (!NativeMethods.GetClientRect(hWnd, out var clientRect))
        {
            return null;
        }

        var clientOrigin = new NativeMethods.POINT { X = 0, Y = 0 };
        if (!NativeMethods.ClientToScreen(hWnd, ref clientOrigin))
        {
            return null;
        }

        var width = Math.Max(0, windowRect.Right - windowRect.Left);
        var height = Math.Max(0, windowRect.Bottom - windowRect.Top);
        var clientWidth = Math.Max(0, clientRect.Right - clientRect.Left);
        var clientHeight = Math.Max(0, clientRect.Bottom - clientRect.Top);
        if (clientWidth <= 0 || clientHeight <= 0)
        {
            return null;
        }

        return new WindowInfo(
            Handle: hWnd,
            ProcessId: process.Id,
            ProcessName: process.ProcessName,
            Title: title,
            Left: windowRect.Left,
            Top: windowRect.Top,
            Width: width,
            Height: height,
            ClientLeft: clientOrigin.X,
            ClientTop: clientOrigin.Y,
            ClientWidth: clientWidth,
            ClientHeight: clientHeight);
    }

    private static string GetWindowTitle(nint hWnd)
    {
        var length = NativeMethods.GetWindowTextLength(hWnd);
        var builder = new StringBuilder(length + 1);
        _ = NativeMethods.GetWindowText(hWnd, builder, builder.Capacity);
        return builder.ToString();
    }

    private static bool MatchesHint(string candidate, string hint)
    {
        if (string.IsNullOrWhiteSpace(hint))
        {
            return true;
        }

        var normalizedCandidate = Normalize(candidate);
        var normalizedHint = Normalize(hint);
        if (string.IsNullOrWhiteSpace(normalizedHint))
        {
            return true;
        }

        return normalizedCandidate.Contains(normalizedHint, StringComparison.OrdinalIgnoreCase);
    }

    private static string Normalize(string value)
    {
        var builder = new StringBuilder(value.Length);
        foreach (var c in value)
        {
            if (char.IsLetterOrDigit(c))
            {
                builder.Append(char.ToLowerInvariant(c));
            }
        }

        return builder.ToString();
    }
}
