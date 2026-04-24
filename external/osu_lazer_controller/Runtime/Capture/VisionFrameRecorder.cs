using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using OsuLazerController.Config;
using OsuLazerController.Models;
using OsuLazerController.Runtime.Win32;

namespace OsuLazerController.Runtime.Capture;

public sealed class VisionFrameRecorder
{
    private readonly VisionCaptureConfig _config;
    private readonly string _outputDirectory;
    private long _capturedFrames;
    private long _savedFrames;
    private double _totalScreenGrabMs;
    private double _totalPostProcessMs;
    private double _totalSaveMs;
    private double _totalFrameMs;

    public VisionFrameRecorder(RuntimeConfig runtimeConfig)
    {
        _config = runtimeConfig.VisionCapture ?? VisionCaptureConfig.Disabled();
        _outputDirectory = Path.Combine(
            AppContext.BaseDirectory,
            runtimeConfig.Logging.Directory,
            "vision_frames",
            $"run_{DateTime.UtcNow:yyyyMMdd_HHmmss}");
    }

    public bool Enabled => _config.Enabled;

    public CapturedVisionFrame? Capture(PlayfieldBounds playfield, long tickIndex)
    {
        if (!ShouldCapture(tickIndex))
        {
            return null;
        }

        var totalTimer = Stopwatch.StartNew();

        var grabTimer = Stopwatch.StartNew();
        using var source = CapturePlayfield(playfield, _config.Width, _config.Height);
        grabTimer.Stop();
        _totalScreenGrabMs += grabTimer.Elapsed.TotalMilliseconds;

        var postProcessTimer = Stopwatch.StartNew();
        using var final = _config.Grayscale ? ToGrayscale(source) : new Bitmap(source);
        var pixels = ExtractPixels(final, _config.Grayscale);
        postProcessTimer.Stop();
        _totalPostProcessMs += postProcessTimer.Elapsed.TotalMilliseconds;

        _capturedFrames++;

        if (ShouldSaveFrame(tickIndex))
        {
            Directory.CreateDirectory(_outputDirectory);
            var outputPath = Path.Combine(
                _outputDirectory,
                $"frame_{_savedFrames + 1:000000}_tick_{tickIndex:000000}.png");
            var saveTimer = Stopwatch.StartNew();
            final.Save(outputPath, ImageFormat.Png);
            saveTimer.Stop();
            _totalSaveMs += saveTimer.Elapsed.TotalMilliseconds;
            _savedFrames++;
        }

        totalTimer.Stop();
        _totalFrameMs += totalTimer.Elapsed.TotalMilliseconds;
        return new CapturedVisionFrame(tickIndex, final.Width, final.Height, _config.Grayscale, pixels);
    }

    public void PrintSummary()
    {
        if (!Enabled || _capturedFrames == 0)
        {
            return;
        }

        var averageTotalMs = _totalFrameMs / _capturedFrames;
        var averageGrabMs = _totalScreenGrabMs / _capturedFrames;
        var averagePostProcessMs = _totalPostProcessMs / _capturedFrames;
        var averageSaveMs = _savedFrames > 0 ? _totalSaveMs / _savedFrames : 0.0;
        Console.WriteLine(
            $"[vision] captured={_capturedFrames} saved={_savedFrames} size={_config.Width}x{_config.Height} " +
            $"grayscale={_config.Grayscale} avgTotalMs={averageTotalMs:0.###} " +
            $"avgGrabMs={averageGrabMs:0.###} avgResizeMs=0 " +
            $"avgPostMs={averagePostProcessMs:0.###} avgSaveMs={averageSaveMs:0.###} dir={_outputDirectory}");
    }

    private bool ShouldCapture(long tickIndex)
    {
        if (!Enabled)
        {
            return false;
        }

        if (_config.MaxCapturedFrames > 0 && _capturedFrames >= _config.MaxCapturedFrames)
        {
            return false;
        }

        var everyNTicks = Math.Max(1, _config.CaptureEveryNTicks);
        return (tickIndex - 1) % everyNTicks == 0;
    }

    private bool ShouldSaveFrame(long tickIndex)
    {
        if (!_config.SaveFrames)
        {
            return false;
        }

        if (_config.MaxSavedFrames > 0 && _savedFrames >= _config.MaxSavedFrames)
        {
            return false;
        }

        var everyNTicks = Math.Max(1, _config.SaveEveryNTicks);
        return (tickIndex - 1) % everyNTicks == 0;
    }

    private Bitmap CapturePlayfield(PlayfieldBounds playfield, int width, int height)
    {
        var bitmap = new Bitmap(width, height, PixelFormat.Format32bppArgb);
        using var graphics = Graphics.FromImage(bitmap);
        var destinationHdc = graphics.GetHdc();
        var screenHdc = NativeMethods.GetDC(nint.Zero);
        try
        {
            var mode = width < playfield.Width || height < playfield.Height
                ? NativeMethods.COLORONCOLOR
                : NativeMethods.HALFTONE;
            NativeMethods.SetStretchBltMode(destinationHdc, mode);
            if (!NativeMethods.StretchBlt(
                    destinationHdc,
                    0,
                    0,
                    width,
                    height,
                    screenHdc,
                    playfield.Left,
                    playfield.Top,
                    playfield.Width,
                    playfield.Height,
                    NativeMethods.SRCCOPY))
            {
                throw new InvalidOperationException("Failed to capture playfield with StretchBlt.");
            }
        }
        finally
        {
            if (screenHdc != nint.Zero)
            {
                _ = NativeMethods.ReleaseDC(nint.Zero, screenHdc);
            }

            graphics.ReleaseHdc(destinationHdc);
        }

        return bitmap;
    }

    private static Bitmap ToGrayscale(Bitmap source)
    {
        var grayscale = new Bitmap(source.Width, source.Height, PixelFormat.Format24bppRgb);
        using var graphics = Graphics.FromImage(grayscale);
        using var attributes = new ImageAttributes();
        attributes.SetColorMatrix(
            new ColorMatrix(
            [
                [0.299f, 0.299f, 0.299f, 0, 0],
                [0.587f, 0.587f, 0.587f, 0, 0],
                [0.114f, 0.114f, 0.114f, 0, 0],
                [0, 0, 0, 1, 0],
                [0, 0, 0, 0, 1],
            ]));
        graphics.DrawImage(
            source,
            new Rectangle(0, 0, grayscale.Width, grayscale.Height),
            0,
            0,
            source.Width,
            source.Height,
            GraphicsUnit.Pixel,
            attributes);
        return grayscale;
    }

    private static byte[] ExtractPixels(Bitmap source, bool grayscale)
    {
        var rect = new Rectangle(0, 0, source.Width, source.Height);
        var data = source.LockBits(rect, ImageLockMode.ReadOnly, source.PixelFormat);
        try
        {
            var stride = data.Stride;
            var raw = new byte[Math.Abs(stride) * source.Height];
            System.Runtime.InteropServices.Marshal.Copy(data.Scan0, raw, 0, raw.Length);

            if (grayscale)
            {
                var pixels = new byte[source.Width * source.Height];
                for (var y = 0; y < source.Height; y++)
                {
                    var rowStart = y * Math.Abs(stride);
                    var destinationStart = y * source.Width;
                    for (var x = 0; x < source.Width; x++)
                    {
                        pixels[destinationStart + x] = raw[rowStart + (x * 3)];
                    }
                }

                return pixels;
            }

            var rgb = new byte[source.Width * source.Height * 3];
            for (var y = 0; y < source.Height; y++)
            {
                var rowStart = y * Math.Abs(stride);
                var destinationStart = y * source.Width * 3;
                Array.Copy(raw, rowStart, rgb, destinationStart, source.Width * 3);
            }

            return rgb;
        }
        finally
        {
            source.UnlockBits(data);
        }
    }
}
