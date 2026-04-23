using System.Text;
using System.Text.Json;
using NetMQ;
using NetMQ.Sockets;
using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Bridge;

public sealed class ZeroMqPolicyBridge : IPolicyBridge, IDisposable
{
    private readonly PolicyBridgeConfig _config;
    private readonly RequestSocket _socket;

    public ZeroMqPolicyBridge(PolicyBridgeConfig config)
    {
        _config = config;
        _socket = new RequestSocket();
        _socket.Options.Linger = TimeSpan.Zero;
        _socket.Connect(_config.Address);
    }

    public Task<ActionPacket> RequestActionAsync(ObservationPacket observation, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();

        var payload = JsonSerializer.Serialize(new { command = "act", obs = observation.Obs });
        var sent = _socket.TrySendFrame(TimeSpan.FromMilliseconds(_config.TimeoutMs), Encoding.UTF8.GetBytes(payload));
        if (!sent)
        {
            throw new TimeoutException($"Timed out sending request to {_config.Address}");
        }

        var received = _socket.TryReceiveFrameBytes(TimeSpan.FromMilliseconds(_config.TimeoutMs), out var responseBytes);
        if (!received || responseBytes is null)
        {
            throw new TimeoutException($"Timed out waiting for response from {_config.Address}");
        }

        using var document = JsonDocument.Parse(responseBytes);
        var root = document.RootElement;
        var ok = root.TryGetProperty("ok", out var okProperty) && okProperty.ValueKind == JsonValueKind.True;
        if (!ok)
        {
            var error = root.TryGetProperty("error", out var errorProperty) ? errorProperty.GetString() : "unknown";
            throw new InvalidOperationException($"Policy bridge error: {error ?? "unknown"}");
        }

        var dx = root.GetProperty("dx").GetDouble();
        var dy = root.GetProperty("dy").GetDouble();
        var clickStrength = root.GetProperty("click_strength").GetDouble();
        return Task.FromResult(new ActionPacket(dx, dy, clickStrength));
    }

    public void Dispose()
    {
        _socket.Dispose();
        NetMQConfig.Cleanup(false);
    }
}
