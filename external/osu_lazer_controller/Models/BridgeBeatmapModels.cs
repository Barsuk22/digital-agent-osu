namespace OsuLazerController.Models;

public sealed record BridgeDifficulty(
    double Hp,
    double Cs,
    double Od,
    double Ar,
    double SliderMultiplier,
    double SliderTickRate);

public sealed record BridgeTimingPoint(
    double TimeMs,
    double BeatLength,
    int Meter,
    int SampleSet,
    int SampleIndex,
    int Volume,
    bool Uninherited,
    int Effects);

public sealed record BridgePoint(double X, double Y);

public sealed record BridgeHitObject(
    int Index,
    string Kind,
    double TimeMs,
    double X,
    double Y,
    int ComboIndex,
    int ComboNumber,
    int Hitsound,
    double? EndTimeMs,
    string? CurveType,
    List<BridgePoint>? ControlPoints,
    int? Repeats,
    double? PixelLength,
    double? DurationMs,
    List<BridgePoint>? SampledPath,
    List<double>? CumulativeLengths,
    double? TotalLength);

public sealed record BridgeBeatmap(
    int SchemaVersion,
    string BeatmapPath,
    string Title,
    string Artist,
    string Version,
    BridgeDifficulty Difficulty,
    List<BridgeTimingPoint> TimingPoints,
    List<BridgeHitObject> HitObjects);
