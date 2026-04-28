using System.Text;
using System.Windows.Forms;
using OsuAgentStudio.Core;

namespace OsuAgentStudio;

internal static class Program
{
    private static readonly string LogDir = Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
        "OsuAgentStudio");

    [STAThread]
    private static async Task Main()
    {
        Directory.CreateDirectory(LogDir);

        File.AppendAllText(
            Path.Combine(LogDir, "studio_crash.log"),
            $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] Crash log initialized.{Environment.NewLine}");

        Application.ThreadException += (_, e) => LogCrash("UI ThreadException", e.Exception);

        AppDomain.CurrentDomain.UnhandledException += (_, e) =>
            LogCrash("AppDomain UnhandledException", e.ExceptionObject as Exception);

        TaskScheduler.UnobservedTaskException += (_, e) =>
        {
            LogCrash("TaskScheduler UnobservedTaskException", e.Exception);
            e.SetObserved();
        };

        try
        {
            ApplicationConfiguration.Initialize();

            LogInfo("Studio starting.");

            var updateStarted = await UpdateManager.CheckForUpdatesOnStartupAsync();
            if (updateStarted)
                return;

            Application.Run(new MainForm());

            LogInfo("Studio closed normally.");
        }
        catch (Exception ex)
        {
            LogCrash("Main fatal exception", ex);

            MessageBox.Show(
                ex.ToString(),
                "OsuAgentStudio fatal error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }

    private static void LogInfo(string text)
    {
        File.AppendAllText(
            Path.Combine(LogDir, "studio.log"),
            $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {text}{Environment.NewLine}",
            Encoding.UTF8);
    }

    private static void LogCrash(string title, Exception? ex)
    {
        var text =
            $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {title}{Environment.NewLine}" +
            $"{ex}{Environment.NewLine}{new string('-', 90)}{Environment.NewLine}";

        File.AppendAllText(Path.Combine(LogDir, "studio_crash.log"), text, Encoding.UTF8);
    }
}
