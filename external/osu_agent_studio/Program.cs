using System.Windows.Forms;

namespace OsuAgentStudio;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        try
        {
            ApplicationConfiguration.Initialize();
            Application.Run(new MainForm());
        }
        catch (Exception ex)
        {
            try
            {
                var logDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "OsuAgentStudio");
                Directory.CreateDirectory(logDir);
                File.WriteAllText(Path.Combine(logDir, "startup_error.txt"), ex.ToString());
            }
            catch
            {
                // Ignore secondary logging failures.
            }

            MessageBox.Show(
                ex.ToString(),
                "OsuAgentStudio startup error",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}
