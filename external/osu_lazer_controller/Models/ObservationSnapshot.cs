namespace OsuLazerController.Models;

public sealed record ObservationSnapshot(
    double MapTimeMs,
    double CursorX,
    double CursorY,
    float[] Vector,
    IReadOnlyList<BridgeHitObject> Upcoming,
    bool ActiveSlider,
    bool ActiveSpinner,
    string PrimaryObjectKind,
    double AssistTargetX,
    double AssistTargetY);
