using System.Text.Json;

namespace OsuLazerController.Config;

public sealed record PolicyBridgeConfig(
    string Mode,
    string Address,
    string ModelPath,
    int ObservationSize,
    int TimeoutMs);

public sealed record TimingConfig(
    double TickRateHz,
    double StartupDelayMs,
    int DiagnosticTicks,
    double DiagnosticInitialMapTimeMs,
    string StartTriggerMode,
    string StartHotkey,
    double AudioOffsetMs,
    double InputDelayMs,
    double CaptureDelayMs);

public sealed record WindowConfig(
    string TitleHint,
    string ProcessName,
    bool RequireForeground,
    string ExecutablePath);

public sealed record LoggingConfig(
    bool Enabled,
    string Directory,
    bool SaveJsonTrace);

public sealed record BeatmapConfig(
    string SourceOsuPath,
    string ExportJsonPath);

public sealed record ControlConfig(
    bool EnableMouseMovement,
    bool EnableMouseClicks,
    bool RecenterCursorOnStart,
    bool UseLiveCursorTracking,
    double PlayfieldPadX,
    double PlayfieldPadY,
    double CursorSpeedScale,
    double AimAssistStrength,
    double AimAssistMaxDistance,
    double AimAssistDeadzone,
    double ClickThreshold,
    double SliderHoldThreshold,
    double SpinnerHoldThreshold);

public sealed record RuntimeConfig(
    PolicyBridgeConfig PolicyBridge,
    TimingConfig Timing,
    WindowConfig Window,
    BeatmapConfig Beatmap,
    ControlConfig Control,
    LoggingConfig Logging)
{
    public static RuntimeConfig Load(string? configPath = null)
    {
        var resolvedPath = string.IsNullOrWhiteSpace(configPath)
            ? Path.Combine(AppContext.BaseDirectory, "configs", "runtime.json")
            : Path.GetFullPath(configPath);
        if (!File.Exists(resolvedPath))
        {
            return Defaults();
        }

        var json = File.ReadAllText(resolvedPath);
        return JsonSerializer.Deserialize<RuntimeConfig>(json, JsonOptions()) ?? Defaults();
    }

    public static RuntimeConfig Defaults() =>
        new(
            new PolicyBridgeConfig(
                Mode: "zeromq",
                Address: "tcp://127.0.0.1:5555",
                ModelPath: @"D:\Projects\digital_agent_osu_project\artifacts\exports\onnx\best_easy_generalization.onnx",
                ObservationSize: 59,
                TimeoutMs: 1000),
            new TimingConfig(
                TickRateHz: 60.0,
                StartupDelayMs: 1000.0,
                DiagnosticTicks: 12,
                DiagnosticInitialMapTimeMs: 1800.0,
                StartTriggerMode: "delay",
                StartHotkey: "F8",
                AudioOffsetMs: 0.0,
                InputDelayMs: 0.0,
                CaptureDelayMs: 0.0),
            new WindowConfig(
                TitleHint: "osu!",
                ProcessName: "osu!",
                RequireForeground: true,
                ExecutablePath: @"C:\Users\valer\AppData\Local\osulazer\current\osu!.exe"),
            new BeatmapConfig(
                SourceOsuPath: @"D:\Projects\digital_agent_osu_project\data\raw\osu\maps\StylipS - Spica\StylipS - Spica. (TV-size) (Lanturn) [Beginner-ka].osu",
                ExportJsonPath: @"D:\Projects\digital_agent_osu_project\exports\osu_lazer_bridge_map.json"),
            new ControlConfig(
                EnableMouseMovement: false,
                EnableMouseClicks: false,
                RecenterCursorOnStart: false,
                UseLiveCursorTracking: false,
                PlayfieldPadX: 80.0,
                PlayfieldPadY: 60.0,
                CursorSpeedScale: 14.0,
                AimAssistStrength: 0.0,
                AimAssistMaxDistance: 160.0,
                AimAssistDeadzone: 18.0,
                ClickThreshold: 0.75,
                SliderHoldThreshold: 0.45,
                SpinnerHoldThreshold: 0.45),
            new LoggingConfig(
                Enabled: true,
                Directory: "logs",
                SaveJsonTrace: true));

    private static JsonSerializerOptions JsonOptions() =>
        new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            ReadCommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true,
        };
}
