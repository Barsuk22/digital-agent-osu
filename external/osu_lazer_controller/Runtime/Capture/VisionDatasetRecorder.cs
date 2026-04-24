using System.Text.Json;
using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Capture;

public sealed class VisionDatasetRecorder : IDisposable
{
    private readonly VisionDatasetConfig _config;
    private readonly string _datasetDirectory;
    private readonly string _runId;
    private readonly string _datasetPath;
    private readonly string _metadataPath;
    private readonly FileStream? _stream;
    private readonly BinaryWriter? _writer;
    private long _recordedFrames;
    private long _skippedFrames;

    public VisionDatasetRecorder(RuntimeConfig runtimeConfig)
    {
        _config = runtimeConfig.VisionDataset ?? VisionDatasetConfig.Disabled();
        _runId = DateTime.UtcNow.ToString("yyyyMMdd_HHmmss");
        _datasetDirectory = Path.Combine(
            AppContext.BaseDirectory,
            runtimeConfig.Logging.Directory,
            _config.Directory,
            $"run_{_runId}");
        _datasetPath = Path.Combine(_datasetDirectory, "vision_dataset.bin");
        _metadataPath = Path.Combine(_datasetDirectory, "metadata.json");

        if (!Enabled)
        {
            return;
        }

        Directory.CreateDirectory(_datasetDirectory);
        _stream = new FileStream(_datasetPath, FileMode.Create, FileAccess.Write, FileShare.Read);
        _writer = new BinaryWriter(_stream);
        WriteHeader(runtimeConfig);
    }

    public bool Enabled => _config.Enabled;

    public string DatasetPath => _datasetPath;

    public string MetadataPath => _metadataPath;

    public void Record(
        CapturedVisionFrame? frame,
        ObservationSnapshot snapshot,
        ActionPacket action,
        RuntimeTick runtimeTick)
    {
        if (!Enabled)
        {
            return;
        }

        if (frame is null)
        {
            _skippedFrames++;
            return;
        }

        if (!ShouldRecord(frame.TickIndex))
        {
            _skippedFrames++;
            return;
        }

        _writer!.Write(frame.TickIndex);
        _writer.Write(snapshot.MapTimeMs);
        _writer.Write(frame.Width);
        _writer.Write(frame.Height);
        _writer.Write(frame.Grayscale);
        _writer.Write(frame.Pixels.Length);
        _writer.Write(frame.Pixels);

        _writer.Write(snapshot.Vector.Length);
        foreach (var value in snapshot.Vector)
        {
            _writer.Write(value);
        }

        _writer.Write(action.Dx);
        _writer.Write(action.Dy);
        _writer.Write(action.ClickStrength);

        _writer.Write(snapshot.CursorX);
        _writer.Write(snapshot.CursorY);
        _writer.Write(runtimeTick.AppliedCursorX);
        _writer.Write(runtimeTick.AppliedCursorY);
        _writer.Write(runtimeTick.TrackedCursorX);
        _writer.Write(runtimeTick.TrackedCursorY);
        _writer.Write(runtimeTick.TrackedCursorValid);
        _writer.Write(runtimeTick.ActiveSlider);
        _writer.Write(runtimeTick.ActiveSpinner);
        _writer.Write(runtimeTick.JustPressed);
        _writer.Write(runtimeTick.RawClickDown);
        _writer.Write(runtimeTick.SliderHoldDown);
        _writer.Write(runtimeTick.SpinnerHoldDown);
        _writer.Write(runtimeTick.ClickDown);
        _writer.Write(runtimeTick.PrimaryObject);

        _recordedFrames++;
    }

    public void PrintSummary()
    {
        if (!Enabled)
        {
            return;
        }

        Console.WriteLine(
            $"[vision-dataset] frames={_recordedFrames} skipped={_skippedFrames} " +
            $"bin={_datasetPath} meta={_metadataPath}");
    }

    public void Dispose()
    {
        if (!Enabled)
        {
            return;
        }

        WriteMetadata();
        _writer?.Dispose();
        _stream?.Dispose();
    }

    private bool ShouldRecord(long tickIndex)
    {
        if (_config.MaxFrames > 0 && _recordedFrames >= _config.MaxFrames)
        {
            return false;
        }

        var everyNTicks = Math.Max(1, _config.SaveEveryNTicks);
        return (tickIndex - 1) % everyNTicks == 0;
    }

    private void WriteHeader(RuntimeConfig runtimeConfig)
    {
        _writer!.Write("OSU_VISION_DATASET_V1");
        _writer.Write(_runId);
        _writer.Write(runtimeConfig.PolicyBridge.ObservationSize);
        _writer.Write(runtimeConfig.Timing.TickRateHz);
        _writer.Write(runtimeConfig.Control.CursorSpeedScale);
        _writer.Write(runtimeConfig.Control.EnableMouseMovement);
        _writer.Write(runtimeConfig.Control.EnableMouseClicks);
    }

    private void WriteMetadata()
    {
        var payload = new
        {
            version = 1,
            runId = _runId,
            recordedFrames = _recordedFrames,
            skippedFrames = _skippedFrames,
            datasetPath = _datasetPath,
            createdAtUtc = DateTime.UtcNow,
        };

        File.WriteAllText(
            _metadataPath,
            JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }));
    }
}
