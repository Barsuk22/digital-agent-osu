using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Bridge;

public interface IPolicyBridge : IDisposable
{
    Task<ActionPacket> RequestActionAsync(ObservationPacket observation, CancellationToken cancellationToken = default);
}
