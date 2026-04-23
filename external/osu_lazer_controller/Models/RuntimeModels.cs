namespace OsuLazerController.Models;

public sealed record ObservationPacket(float[] Obs);

public sealed record ActionPacket(double Dx, double Dy, double ClickStrength);

public sealed record RuntimeTick(
    long TickIndex,
    double MapTimeMs,
    double CursorX,
    double CursorY,
    float[] Observation,
    string PrimaryObject,
    bool ActiveSlider,
    bool ActiveSpinner,
    double AssistTargetX,
    double AssistTargetY,
    double LoopElapsedMs,
    double PolicyLatencyMs,
    ActionPacket Action,
    double AppliedCursorX,
    double AppliedCursorY,
    double TrackedCursorX,
    double TrackedCursorY,
    bool TrackedCursorValid,
    bool JustPressed,
    bool RawClickDown,
    bool SliderHoldDown,
    bool SpinnerHoldDown,
    bool ClickDown);

public sealed record WindowInfo(
    nint Handle,
    int ProcessId,
    string ProcessName,
    string Title,
    int Left,
    int Top,
    int Width,
    int Height,
    int ClientLeft,
    int ClientTop,
    int ClientWidth,
    int ClientHeight);
