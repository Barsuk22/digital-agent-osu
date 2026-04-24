using System.Diagnostics;

namespace OsuLazerController.Runtime.Beatmaps;

public sealed class BridgeBeatmapExporter
{
    public bool TryExport(string osuPath, string outputJsonPath)
    {
        var projectRoot = FindProjectRoot();
        if (projectRoot is null)
        {
            Console.WriteLine("[beatmap-auto] project root not found; cannot run bridge exporter");
            return false;
        }

        Directory.CreateDirectory(Path.GetDirectoryName(outputJsonPath) ?? projectRoot);
        var startInfo = new ProcessStartInfo
        {
            FileName = "python",
            WorkingDirectory = projectRoot,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
        };
        startInfo.ArgumentList.Add("-m");
        startInfo.ArgumentList.Add("src.apps.export_osu_lazer_bridge_map");
        startInfo.ArgumentList.Add("--map");
        startInfo.ArgumentList.Add(osuPath);
        startInfo.ArgumentList.Add("--out");
        startInfo.ArgumentList.Add(outputJsonPath);

        try
        {
            using var process = Process.Start(startInfo);
            if (process is null)
            {
                Console.WriteLine("[beatmap-auto] failed to start python exporter");
                return false;
            }

            var output = process.StandardOutput.ReadToEnd();
            var error = process.StandardError.ReadToEnd();
            process.WaitForExit();

            if (!string.IsNullOrWhiteSpace(output))
            {
                Console.WriteLine(output.Trim());
            }

            if (process.ExitCode == 0 && File.Exists(outputJsonPath))
            {
                return true;
            }

            if (!string.IsNullOrWhiteSpace(error))
            {
                Console.WriteLine(error.Trim());
            }

            Console.WriteLine($"[beatmap-auto] exporter failed with exit code {process.ExitCode}");
            return false;
        }
        catch (Exception ex)
        {
            Console.WriteLine($"[beatmap-auto] exporter error: {ex.Message}");
            return false;
        }
    }

    private static string? FindProjectRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            if (Directory.Exists(Path.Combine(current.FullName, "src"))
                && Directory.Exists(Path.Combine(current.FullName, "external")))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return null;
    }
}
