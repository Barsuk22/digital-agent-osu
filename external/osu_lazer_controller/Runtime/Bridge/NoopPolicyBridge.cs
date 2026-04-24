using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Bridge;

public sealed class NoopPolicyBridge : IPolicyBridge
{
    public Task<ActionPacket> RequestActionAsync(ObservationPacket observation, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();
        return Task.FromResult(new ActionPacket(0.0, 0.0, 0.0));
    }

    public void Dispose()
    {
    }
}
