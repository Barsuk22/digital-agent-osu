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
    bool SaveJsonTrace,
    int TickConsoleEveryNTicks);

public sealed record VisionCaptureConfig(
    bool Enabled,
    int Width,
    int Height,
    bool Grayscale,
    int CaptureEveryNTicks,
    int MaxCapturedFrames,
    bool SaveFrames,
    int SaveEveryNTicks,
    int MaxSavedFrames)
{
    public static VisionCaptureConfig Disabled() =>
        new(
            Enabled: false,
            Width: 96,
            Height: 72,
            Grayscale: true,
            CaptureEveryNTicks: 1,
            MaxCapturedFrames: 0,
            SaveFrames: false,
            SaveEveryNTicks: 120,
            MaxSavedFrames: 12);
}

public sealed record VisionDatasetConfig(
    bool Enabled,
    string Directory,
    int SaveEveryNTicks,
    int MaxFrames)
{
    public static VisionDatasetConfig Disabled() =>
        new(
            Enabled: false,
            Directory: "vision_dataset",
            SaveEveryNTicks: 1,
            MaxFrames: 0);
}

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
    double PlayfieldScaleX,
    double PlayfieldScaleY,
    double PlayfieldOffsetX,
    double PlayfieldOffsetY,
    double CursorSpeedScale,
    double ActionSmoothing,
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
    LoggingConfig Logging,
    VisionCaptureConfig? VisionCapture,
    VisionDatasetConfig? VisionDataset)
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
        var config = JsonSerializer.Deserialize<RuntimeConfig>(json, JsonOptions()) ?? Defaults();
        return config with
        {
            VisionCapture = config.VisionCapture ?? VisionCaptureConfig.Disabled(),
            VisionDataset = config.VisionDataset ?? VisionDatasetConfig.Disabled(),
            Control = NormalizeControlConfig(config.Control),
        };
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
                PlayfieldScaleX: 1.0,
                PlayfieldScaleY: 1.0,
                PlayfieldOffsetX: 0.0,
                PlayfieldOffsetY: 0.0,
                CursorSpeedScale: 14.0,
                ActionSmoothing: 0.0,
                AimAssistStrength: 0.0,
                AimAssistMaxDistance: 160.0,
                AimAssistDeadzone: 18.0,
                ClickThreshold: 0.75,
                SliderHoldThreshold: 0.45,
                SpinnerHoldThreshold: 0.45),
            new LoggingConfig(
                Enabled: true,
                Directory: "logs",
                SaveJsonTrace: true,
                TickConsoleEveryNTicks: 0),
            VisionCaptureConfig.Disabled(),
            VisionDatasetConfig.Disabled());

    private static JsonSerializerOptions JsonOptions() =>
        new()
        {
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
            ReadCommentHandling = JsonCommentHandling.Skip,
            AllowTrailingCommas = true,
        };

    private static ControlConfig NormalizeControlConfig(ControlConfig config) =>
        config with
        {
            PlayfieldScaleX = config.PlayfieldScaleX > 0.0 ? config.PlayfieldScaleX : 1.0,
            PlayfieldScaleY = config.PlayfieldScaleY > 0.0 ? config.PlayfieldScaleY : 1.0,
        };
}
