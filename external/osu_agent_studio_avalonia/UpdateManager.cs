using System.Diagnostics;
using System.Reflection;
using System.Text.Json;
using Avalonia.Controls;
using Avalonia.Layout;
using Avalonia.Media;
using OsuAgentStudio.Core;

namespace OsuAgentStudio.Avalonia;

public static class UpdateManager
{
    private const string ManifestUrl =
        "https://raw.githubusercontent.com/Barsuk22/osu-agent-bundles/main/bundle_manifest.json";

    public static async Task<bool> CheckForUpdatesOnStartupAsync(Window owner)
    {
        try
        {
            using var http = new HttpClient();
            var json = await http.GetStringAsync(ManifestUrl);
            var manifest = JsonSerializer.Deserialize<BundleManifest>(json);

            if (manifest?.version is null || string.IsNullOrWhiteSpace(manifest.bundleZipUrl))
                return false;

            var current = Assembly.GetExecutingAssembly().GetName().Version ?? new Version(1, 0, 0);
            var remote = Version.Parse(manifest.version);

            if (remote <= current)
                return false;

            var accepted = await ShowUpdateDialogAsync(owner, manifest.version, manifest.notes);
            if (!accepted)
                return false;

            var root = StudioPaths.ProjectRoot;
            var script = Path.Combine(root, "scripts", "update_osu_agent_bundle.ps1");

            if (!File.Exists(script))
            {
                await ShowInfoDialogAsync(owner, "Update error", $"Updater not found:\n{script}");
                return false;
            }

            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments =
                    $"-ExecutionPolicy Bypass -File \"{script}\" -InstallDir \"{root}\" -ManifestUrl \"{ManifestUrl}\" -WaitSeconds 6",
                UseShellExecute = true,
                WindowStyle = ProcessWindowStyle.Normal
            };

            Process.Start(psi);
            await Task.Delay(500);
            Process.GetCurrentProcess().Kill();
            return true;
        }
        catch (Exception ex)
        {
            await ShowInfoDialogAsync(owner, "Update check failed", ex.ToString());
            return false;
        }
    }

    private static Task<bool> ShowUpdateDialogAsync(Window owner, string version, string? notes)
    {
        var dialog = CreateDialog(
            "Osu Agent Update",
            $"Доступно обновление v{version}.\n\nСкачать, установить и перезапустить приложение?\n\n{notes}".Trim(),
            includeCancel: true);

        return dialog.ShowDialog<bool>(owner);
    }

    private static Task ShowInfoDialogAsync(Window owner, string title, string text)
    {
        var dialog = CreateDialog(title, text, includeCancel: false);
        return dialog.ShowDialog<bool>(owner);
    }

    private static Window CreateDialog(string title, string text, bool includeCancel)
    {
        var buttons = new StackPanel
        {
            Orientation = Orientation.Horizontal,
            HorizontalAlignment = HorizontalAlignment.Right,
            Spacing = 10,
            [Grid.RowProperty] = 1,
        };
        buttons.Children.Add(CreateDialogButton(includeCancel ? "Update" : "OK", true));
        if (includeCancel)
            buttons.Children.Add(CreateDialogButton("Later", false));

        var dialog = new Window
        {
            Title = title,
            Width = 520,
            Height = 260,
            MinWidth = 460,
            MinHeight = 220,
            WindowStartupLocation = WindowStartupLocation.CenterOwner,
            Background = new SolidColorBrush(Color.Parse("#070912")),
            Content = new Grid
            {
                RowDefinitions = new RowDefinitions("*,Auto"),
                Margin = new global::Avalonia.Thickness(20),
                Children =
                {
                    new TextBlock
                    {
                        Text = text,
                        TextWrapping = TextWrapping.Wrap,
                        Foreground = new SolidColorBrush(Color.Parse("#F4F7FF")),
                        FontSize = 15,
                    },
                    buttons
                }
            }
        };

        return dialog;
    }

    private static Button CreateDialogButton(string text, bool result)
    {
        var button = new Button
        {
            Content = text,
            MinWidth = 96,
            Height = 36,
            Background = new SolidColorBrush(Color.Parse(result ? "#171B2C" : "#111422")),
            Foreground = new SolidColorBrush(Color.Parse(result ? "#57CAFF" : "#99A2C3")),
            BorderBrush = new SolidColorBrush(Color.Parse(result ? "#57CAFF" : "#2A304A")),
            BorderThickness = new global::Avalonia.Thickness(1),
        };
        button.Click += (_, _) =>
        {
            if (TopLevel.GetTopLevel(button) is Window window)
                window.Close(result);
        };
        return button;
    }

    private sealed class BundleManifest
    {
        public string? version { get; set; }
        public string? bundleZipUrl { get; set; }
        public string? notes { get; set; }
    }
}
