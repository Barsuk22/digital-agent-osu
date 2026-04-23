using System.Drawing;
using System.Drawing.Imaging;
using System.Runtime.InteropServices;
using OsuLazerController.Models;
using OsuLazerController.Runtime.Win32;

namespace OsuLazerController.Runtime.Capture;

public sealed class ScreenCapture
{
    public string CaptureClientArea(WindowInfo window, string outputPath)
    {
        using var bitmap = TryCaptureWindow(window) ?? CaptureFromScreen(window);
        bitmap.Save(outputPath, ImageFormat.Png);
        return outputPath;
    }

    private static Bitmap CaptureFromScreen(WindowInfo window)
    {
        var bitmap = new Bitmap(window.ClientWidth, window.ClientHeight);
        using var graphics = Graphics.FromImage(bitmap);
        graphics.CopyFromScreen(
            sourceX: window.ClientLeft,
            sourceY: window.ClientTop,
            destinationX: 0,
            destinationY: 0,
            blockRegionSize: new Size(window.ClientWidth, window.ClientHeight));
        return bitmap;
    }

    private static Bitmap? TryCaptureWindow(WindowInfo window)
    {
        var fullBitmap = new Bitmap(window.Width, window.Height);
        using var graphics = Graphics.FromImage(fullBitmap);
        var hdc = graphics.GetHdc();
        try
        {
            var printed = NativeMethods.PrintWindow(window.Handle, hdc, NativeMethods.PW_RENDERFULLCONTENT);
            if (!printed)
            {
                return null;
            }
        }
        finally
        {
            graphics.ReleaseHdc(hdc);
        }

        var clientOffsetX = Math.Max(0, window.ClientLeft - window.Left);
        var clientOffsetY = Math.Max(0, window.ClientTop - window.Top);
        var cropWidth = Math.Min(window.ClientWidth, fullBitmap.Width - clientOffsetX);
        var cropHeight = Math.Min(window.ClientHeight, fullBitmap.Height - clientOffsetY);

        if (cropWidth <= 0 || cropHeight <= 0)
        {
            fullBitmap.Dispose();
            return null;
        }

        var clientBitmap = new Bitmap(cropWidth, cropHeight);
        using var cropGraphics = Graphics.FromImage(clientBitmap);
        cropGraphics.DrawImage(
            fullBitmap,
            new Rectangle(0, 0, cropWidth, cropHeight),
            new Rectangle(clientOffsetX, clientOffsetY, cropWidth, cropHeight),
            GraphicsUnit.Pixel);
        fullBitmap.Dispose();
        return clientBitmap;
    }
}
