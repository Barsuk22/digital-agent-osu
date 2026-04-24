using System.Text.Json;
using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Logging;

public sealed class TraceLogger : IDisposable
{
    private readonly RuntimeConfig _config;
    private readonly List<RuntimeTick> _ticks = [];
    private bool _disposed;

    public TraceLogger(RuntimeConfig config)
    {
        _config = config;
        Console.CancelKeyPress += OnCancelKeyPress;
        AppDomain.CurrentDomain.ProcessExit += OnProcessExit;
    }

    public void Append(RuntimeTick tick)
    {
        if (!_config.Logging.Enabled)
        {
            return;
        }

        _ticks.Add(tick);
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;
        Console.CancelKeyPress -= OnCancelKeyPress;
        AppDomain.CurrentDomain.ProcessExit -= OnProcessExit;
        Save();
    }

    private void Save()
    {
        if (!_config.Logging.Enabled || !_config.Logging.SaveJsonTrace || _ticks.Count == 0)
        {
            return;
        }

        var logDir = Path.Combine(AppContext.BaseDirectory, _config.Logging.Directory);
        Directory.CreateDirectory(logDir);
        var output = Path.Combine(logDir, $"warmup_trace_{DateTime.UtcNow:yyyyMMdd_HHmmss}.json");
        var json = JsonSerializer.Serialize(_ticks, new JsonSerializerOptions { WriteIndented = true });
        File.WriteAllText(output, json);
    }

    private void OnCancelKeyPress(object? sender, ConsoleCancelEventArgs args)
    {
        Save();
    }

    private void OnProcessExit(object? sender, EventArgs args)
    {
        Save();
    }
}
