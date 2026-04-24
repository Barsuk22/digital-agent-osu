using System.Diagnostics;

namespace OsuAgentStudio;

internal sealed class ManagedProcess
{
    private Process? _process;

    public event Action<string>? OutputReceived;
    public event Action<string>? StatusChanged;

    public bool IsRunning => _process is { HasExited: false };

    public void Start(string name, string fileName, IEnumerable<string> args, string workingDirectory)
    {
        if (IsRunning)
        {
            OutputReceived?.Invoke($"[{name}] already running.");
            return;
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = fileName,
            WorkingDirectory = workingDirectory,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };

        foreach (var arg in args)
        {
            startInfo.ArgumentList.Add(arg);
        }

        var process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
        process.OutputDataReceived += (_, e) => Emit(name, e.Data);
        process.ErrorDataReceived += (_, e) => Emit(name, e.Data);
        process.Exited += (_, _) =>
        {
            var code = process.ExitCode;
            OutputReceived?.Invoke($"[{name}] exited with code {code}.");
            StatusChanged?.Invoke("Idle");
            process.Dispose();
            if (ReferenceEquals(_process, process))
            {
                _process = null;
            }
        };

        _process = process;
        process.Start();
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        StatusChanged?.Invoke($"{name} running");
        OutputReceived?.Invoke($"[{name}] started: {fileName} {string.Join(" ", args)}");
    }

    public void Stop(string name)
    {
        if (!IsRunning || _process is null)
        {
            OutputReceived?.Invoke($"[{name}] is not running.");
            return;
        }

        try
        {
            _process.Kill(entireProcessTree: true);
            OutputReceived?.Invoke($"[{name}] stop requested.");
        }
        catch (Exception ex)
        {
            OutputReceived?.Invoke($"[{name}] stop failed: {ex.Message}");
        }
    }

    private void Emit(string name, string? line)
    {
        if (!string.IsNullOrWhiteSpace(line))
        {
            OutputReceived?.Invoke($"[{name}] {line}");
        }
    }
}
