using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using OsuAgentStudio.Core;

namespace OsuAgentStudio;

public static class UpdateManager
{
    private const string ManifestUrl =
        "https://raw.githubusercontent.com/Barsuk22/osu-agent-bundles/main/bundle_manifest.json";

    public static async Task<bool> CheckForUpdatesOnStartupAsync()
    {
        try
        {
            using var http = new HttpClient();
            var json = await http.GetStringAsync(ManifestUrl);
            var manifest = JsonSerializer.Deserialize<BundleManifest>(json);

            if (manifest?.version is null || string.IsNullOrWhiteSpace(manifest.bundleZipUrl))
                return false;

            var current = Assembly.GetExecutingAssembly().GetName().Version ?? new Version(1, 0, 0);
            var currentProcess = Process.GetCurrentProcess();

            var remote = Version.Parse(manifest.version);

            if (remote <= current)
                return false;

            var result = MessageBox.Show(
                $"Доступно обновление v{manifest.version}.\n\nСкачать, установить и перезапустить приложение?",
                "Osu Agent Update",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Information);

            if (result != DialogResult.Yes)
                return false;

            var root = StudioPaths.ProjectRoot;
            var script = Path.Combine(root, "scripts", "update_osu_agent_bundle.ps1");

            if (!File.Exists(script))
            {
                MessageBox.Show(
                    $"Не найден updater:\n{script}",
                    "Update error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error);
                return false;
            }

            var exe = Application.ExecutablePath;

            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments =
                    $"-ExecutionPolicy Bypass -File \"{script}\" -InstallDir \"{root}\" -ManifestUrl \"{ManifestUrl}\" -WaitSeconds 6",
                UseShellExecute = true,
                WindowStyle = ProcessWindowStyle.Normal
            };

            Process.Start(psi);

            // чуть подождать, чтобы скрипт успел стартануть
            await Task.Delay(500);

            // УБИВАЕМ СЕБЯ
            currentProcess.Kill();

            return true;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                ex.ToString(),
                "Update check failed",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);

            return false;
        }
    }

    private sealed class BundleManifest
    {
        public string? version { get; set; }
        public string? bundleZipUrl { get; set; }
        public string? notes { get; set; }
    }
}
