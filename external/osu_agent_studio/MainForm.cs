using System.Diagnostics;
using System.Drawing.Drawing2D;

namespace OsuAgentStudio;

public sealed class MainForm : Form
{
    private readonly StudioState _state;
    private readonly ManagedProcess _controller = new();
    private readonly ManagedProcess _training = new();
    private readonly ManagedProcess _export = new();

    private readonly RichTextBox _log = new();
    private readonly ComboBox _configCombo = new();
    private readonly TextBox _mapsFolder = new();
    private readonly CheckedListBox _mapsList = new();
    private readonly NumericUpDown _updates = new();
    private readonly NumericUpDown _saveEvery = new();
    private readonly NumericUpDown _cursorSpeed = new();
    private readonly NumericUpDown _learningRate = new();
    private readonly CheckBox _resetBest = new();
    private readonly Label _mapsStatus = new();
    private readonly Label _agentChip = new();
    private readonly Label _trainChip = new();
    private readonly Label _exportChip = new();
    private readonly Label _filesChip = new();
    private readonly Panel _tabContent = new();
    private readonly List<Button> _tabButtons = new();
    private bool _trainingControlsInitialized;
    private bool _restoringState;
    private int _currentTabIndex;

    private static readonly Color Back = Color.FromArgb(7, 10, 18);
    private static readonly Color Surface = Color.FromArgb(14, 20, 33);
    private static readonly Color Surface2 = Color.FromArgb(20, 28, 45);
    private static readonly Color Stroke = Color.FromArgb(38, 51, 78);
    private static readonly Color TextMain = Color.FromArgb(242, 248, 255);
    private static readonly Color TextMuted = Color.FromArgb(151, 166, 190);
    private static readonly Color Cyan = Color.FromArgb(0, 220, 205);
    private static readonly Color Pink = Color.FromArgb(255, 72, 151);
    private static readonly Color Yellow = Color.FromArgb(255, 205, 75);
    private static readonly Color Blue = Color.FromArgb(112, 130, 255);
    private static readonly Color Green = Color.FromArgb(132, 238, 165);
    private static readonly Color Red = Color.FromArgb(255, 86, 122);

    public MainForm()
    {
        _state = StudioStateStore.Load();
        StudioStateStore.Save(_state);
        Text = "osu! Agent Studio";
        MinimumSize = new Size(1180, 760);
        Size = new Size(_state.WindowWidth, _state.WindowHeight);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Back;
        Font = new Font("Segoe UI", 10f);
        _mapsFolder.Text = string.IsNullOrWhiteSpace(_state.MapsFolder) ? StudioPaths.MapsDir : _state.MapsFolder;

        WireProcess(_controller, _agentChip, "Agent");
        WireProcess(_training, _trainChip, "Training");
        WireProcess(_export, _exportChip, "Export");

        BuildUi();
        HookStatePersistence();
        RefreshConfigList();
        RefreshMaps();
        RefreshStatus();
        ApplyWindowState();
        ShowTabByIndex(Math.Clamp(_state.SelectedTabIndex, 0, 3));
        Shown += (_, _) => ActivateWindowOnLaunch();
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        SaveUiState();
        StopControllerProcesses();
        _training.Stop("training");
        _export.Stop("export");
        base.OnFormClosing(e);
    }

    private void BuildUi()
    {
        var root = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 3,
            ColumnCount = 1,
            BackColor = Back,
            Padding = new Padding(20),
        };
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 94));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 62));
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 38));
        Controls.Add(root);

        root.Controls.Add(BuildTopBar(), 0, 0);
        root.Controls.Add(BuildTabs(), 0, 1);
        root.Controls.Add(BuildConsole(), 0, 2);
    }

    private Control BuildTopBar()
    {
        var top = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            RowCount = 1,
            BackColor = Color.Transparent,
            Margin = new Padding(0),
            Padding = new Padding(0),
        };

        top.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));   // title
        top.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 480));  // nav
        top.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 600));  // chips

        var title = new Label
        {
            Text = "osu! Agent Studio",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 30f),
            TextAlign = ContentAlignment.MiddleLeft,
            Margin = new Padding(0),
        };
        top.Controls.Add(title, 0, 0);

        var nav = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 32, 0, 0),
            Margin = new Padding(0),
            AutoScroll = false,
        };
        nav.Controls.Add(NavButton("Play", Cyan, () => ShowTab(BuildPlayTab, 0)));
        nav.Controls.Add(NavButton("Training", Pink, () => ShowTab(BuildTrainingTab, 1)));
        nav.Controls.Add(NavButton("Export", Yellow, () => ShowTab(BuildExportTab, 2)));
        nav.Controls.Add(NavButton("Files", Blue, () => ShowTab(BuildFilesTab, 3)));
        top.Controls.Add(nav, 1, 0);

        var chips = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 6, 0, 0),
            Margin = new Padding(0),
            AutoScroll = false,
        };
        chips.Controls.Add(MakeChip("Agent", _agentChip, Cyan));
        chips.Controls.Add(MakeChip("Training", _trainChip, Pink));
        chips.Controls.Add(MakeChip("Export", _exportChip, Yellow));
        chips.Controls.Add(MakeChip("Files", _filesChip, Green));
        top.Controls.Add(chips, 2, 0);

        return top;
    }

    private Control BuildTabs()
    {
        _tabContent.Dock = DockStyle.Fill;
        _tabContent.BackColor = Color.Transparent;
        return _tabContent;
    }

    private Control BuildPlayTab()
    {
        var grid = TwoColumns();
        grid.Controls.Add(Card("Live Control", "Start the live agent or oracle. Agent and training can run at the same time.", Cyan, BuildLiveControls()), 0, 0);
        grid.Controls.Add(Card("Runtime Notes", "Recommended flow: start app, choose any map in osu!lazer, press Play. The controller reads osu!lazer logs and syncs to the selected map.", Blue, BuildRuntimeNotes()), 1, 0);
        return grid;
    }

    private Control BuildTrainingTab()
    {
        var grid = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, BackColor = Color.Transparent };
        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 42));
        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 58));
        grid.Controls.Add(Card("Fine-Tune Settings", "Choose maps, set training parameters, then start or stop training.", Pink, BuildTrainingControls()), 0, 0);
        grid.Controls.Add(Card("Training Maps", "Beginner/easy maps are selected by default. You can add a folder and choose exactly what goes into training.", Cyan, BuildMapPicker()), 1, 0);
        return grid;
    }

    private Control BuildExportTab()
    {
        var grid = TwoColumns();
        grid.Controls.Add(Card("Export ONNX", "Export a checkpoint into the model used by live play.", Yellow, BuildExportControls()), 0, 0);
        grid.Controls.Add(Card("Checkpoint Flow", "Train writes latest often. Best changes only when a full map cycle beats the previous best score.", Green, BuildCheckpointNotes()), 1, 0);
        return grid;
    }

    private Control BuildFilesTab()
    {
        var panel = Card("Project Shortcuts", "Open the folders you touch most often.", Blue, BuildFileButtons());
        panel.Dock = DockStyle.Fill;
        return panel;
    }

    private Control BuildLiveControls()
    {
        var body = Stack(8);
        _configCombo.DropDownStyle = ComboBoxStyle.DropDownList;
        StyleCombo(_configCombo);
        body.Controls.Add(Field("Runtime config", _configCombo), 0, 0);
        body.Controls.Add(Button("Launch Agent", Cyan, (_, _) => StartController(GetSelectedConfigOrDefault())), 0, 1);
        body.Controls.Add(Button("Launch Oracle", Color.FromArgb(94, 205, 255), (_, _) => StartController(StudioPaths.OracleConfig)), 0, 2);
        body.Controls.Add(Button("Stop / Kill Agent", Red, (_, _) => StopControllerProcesses()), 0, 3);
        body.Controls.Add(Button("Open Live Logs", Blue, (_, _) => OpenPath(StudioPaths.LogsDir)), 0, 4);
        return body;
    }

    private Control BuildRuntimeNotes()
    {
        return TextBlock(
            "Auto map mode resolves the current osu!lazer map after gameplay starts.\n\n" +
            "Pause/stop events are watched from osu!lazer runtime logs, so the controller releases input instead of playing through menus.\n\n" +
            "Sensitivity in osu!lazer should stay at 1.0.");
    }

    private Control BuildTrainingControls()
    {
        var body = Stack(10);
        if (!_trainingControlsInitialized)
        {
            ConfigureNumber(_updates, 1, 100000, _state.Updates, 0);
            ConfigureNumber(_saveEvery, 10, 1000, _state.SaveEvery, 0);
            ConfigureNumber(_cursorSpeed, 5, 40, _state.CursorSpeed, 1);
            ConfigureNumber(_learningRate, 0.000003m, 0.01m, _state.LearningRate, 6);
            _resetBest.Text = "Reset best metric";
            _resetBest.ForeColor = TextMain;
            _resetBest.BackColor = Color.Transparent;
            _resetBest.Checked = _state.ResetBest;
            _trainingControlsInitialized = true;
        }

        body.Controls.Add(Field("Updates", _updates), 0, 0);
        body.Controls.Add(Field("Save every", _saveEvery), 0, 1);
        body.Controls.Add(Field("Train cursor speed", _cursorSpeed), 0, 2);
        body.Controls.Add(Field("Learning rate", _learningRate), 0, 3);
        body.Controls.Add(_resetBest, 0, 4);
        body.Controls.Add(Button("Start Training", Pink, (_, _) => StartTraining()), 0, 5);
        body.Controls.Add(Button("Stop Training", Red, (_, _) => _training.Stop("training")), 0, 6);
        body.Controls.Add(Button("Open Checkpoints", Blue, (_, _) => OpenPath(StudioPaths.CheckpointsDir)), 0, 7);
        return body;
    }

    private Control BuildMapPicker()
    {
        var body = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 5, ColumnCount = 1, BackColor = Color.Transparent };
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 220));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        body.MinimumSize = new Size(0, 406);

        StyleText(_mapsFolder);
        body.Controls.Add(Field("Maps folder", _mapsFolder), 0, 0);

        var buttons = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 4, RowCount = 1, BackColor = Color.Transparent };
        for (var i = 0; i < 4; i++) buttons.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
        buttons.Controls.Add(Button("Browse", Blue, (_, _) => BrowseMapsFolder()), 0, 0);
        buttons.Controls.Add(Button("Rescan", Cyan, (_, _) => RefreshMaps()), 1, 0);
        buttons.Controls.Add(Button("Select All", Green, (_, _) => SetAllMaps(true)), 2, 0);
        buttons.Controls.Add(Button("Select None", Yellow, (_, _) => SetAllMaps(false)), 3, 0);
        body.Controls.Add(buttons, 0, 1);

        var mapsHost = new Panel
        {
            Dock = DockStyle.Fill,
            MinimumSize = new Size(0, 180),
            BackColor = Color.Transparent,
            Margin = new Padding(0),
            Padding = new Padding(0),
        };
        _mapsList.Dock = DockStyle.Fill;
        _mapsList.BackColor = Color.FromArgb(6, 9, 15);
        _mapsList.ForeColor = TextMain;
        _mapsList.BorderStyle = BorderStyle.FixedSingle;
        _mapsList.CheckOnClick = true;
        _mapsList.IntegralHeight = false;
        _mapsList.HorizontalScrollbar = true;
        mapsHost.Controls.Add(_mapsList);
        body.Controls.Add(mapsHost, 0, 2);

        _mapsStatus.Dock = DockStyle.Fill;
        _mapsStatus.ForeColor = TextMuted;
        _mapsStatus.Text = "Selected maps are passed explicitly to training.";
        _mapsStatus.TextAlign = ContentAlignment.MiddleLeft;
        body.Controls.Add(_mapsStatus, 0, 3);
        body.Controls.Add(Button("Start Training With Selected Maps", Pink, (_, _) => StartTraining()), 0, 4);
        return body;
    }

    private Control BuildExportControls()
    {
        var body = Stack(7);
        body.Controls.Add(Button("Export Latest", Yellow, (_, _) => ExportCheckpoint(StudioPaths.LatestCheckpoint)), 0, 0);
        body.Controls.Add(Button("Export Best", Green, (_, _) => ExportCheckpoint(StudioPaths.BestCheckpoint)), 0, 1);
        body.Controls.Add(Button("Open ONNX Folder", Blue, (_, _) => OpenPath(Path.GetDirectoryName(StudioPaths.OnnxOutput)!)), 0, 2);
        body.Controls.Add(Button("Refresh Status", Cyan, (_, _) => RefreshStatus()), 0, 3);
        return body;
    }

    private Control BuildCheckpointNotes()
    {
        return TextBlock(
            "Use Export Latest when you want to test what is currently learning.\n\n" +
            "Use Export Best when the cycle score actually improved.\n\n" +
            "The live config points to lazer_transfer_generalization.onnx.");
    }

    private Control BuildFileButtons()
    {
        var body = Stack(8);
        body.Controls.Add(Button("Open Maps Folder", Cyan, (_, _) => OpenPath(_mapsFolder.Text)), 0, 0);
        body.Controls.Add(Button("Open Checkpoints", Pink, (_, _) => OpenPath(StudioPaths.CheckpointsDir)), 0, 1);
        body.Controls.Add(Button("Open ONNX Folder", Yellow, (_, _) => OpenPath(Path.GetDirectoryName(StudioPaths.OnnxOutput)!)), 0, 2);
        body.Controls.Add(Button("Open Controller Configs", Blue, (_, _) => OpenPath(StudioPaths.ControllerConfigsDir)), 0, 3);
        body.Controls.Add(Button("Open Runtime Logs", Green, (_, _) => OpenPath(StudioPaths.LogsDir)), 0, 4);
        return body;
    }

    private Control BuildConsole()
    {
        var card = new RoundedPanel { Dock = DockStyle.Fill, Radius = 16, BackColor = Surface, Padding = new Padding(16) };
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 1, BackColor = Color.Transparent };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        card.Controls.Add(layout);

        var head = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, BackColor = Color.Transparent };
        head.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        head.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 170));
        head.Controls.Add(new Label
        {
            Text = "Console",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 15f),
            TextAlign = ContentAlignment.MiddleLeft,
        }, 0, 0);
        head.Controls.Add(Button("Clear Console", Surface2, (_, _) => _log.Clear(), TextMain), 1, 0);
        layout.Controls.Add(head, 0, 0);

        _log.Dock = DockStyle.Fill;
        _log.BackColor = Color.FromArgb(3, 5, 10);
        _log.ForeColor = Color.FromArgb(214, 226, 244);
        _log.BorderStyle = BorderStyle.None;
        _log.Font = new Font("Cascadia Mono", 9.5f);
        _log.ReadOnly = true;
        layout.Controls.Add(_log, 0, 1);
        return card;
    }

    private void StartController(string configPath)
    {
        if (!File.Exists(configPath))
        {
            AppendLog($"Config not found: {configPath}");
            return;
        }

        StopOrphanedControllerProcesses();
        var launcher = StudioPaths.ResolveControllerLaunchPath();
        if (string.Equals(launcher, "dotnet", StringComparison.OrdinalIgnoreCase))
        {
            _controller.Start("agent", "dotnet", new[] { "run", "--project", StudioPaths.ControllerProject, "--", configPath }, StudioPaths.ProjectRoot);
            return;
        }

        var workingDir = Path.GetDirectoryName(launcher) ?? StudioPaths.ProjectRoot;
        _controller.Start("agent", launcher, new[] { configPath }, workingDir);
    }

    private void StopControllerProcesses()
    {
        _controller.Stop("agent");
        StopOrphanedControllerProcesses();
        RefreshStatus();
    }

    private void StopOrphanedControllerProcesses()
    {
        try
        {
            foreach (var process in Process.GetProcessesByName("OsuLazerController"))
            {
                try
                {
                    process.Kill(entireProcessTree: true);
                    AppendLog($"[agent] cleaned leftover controller pid={process.Id}.");
                }
                catch (Exception ex)
                {
                    AppendLog($"[agent] cleanup failed for pid={process.Id}: {ex.Message}");
                }
            }
        }
        catch (Exception ex)
        {
            AppendLog($"[agent] controller cleanup failed: {ex.Message}");
        }
    }

    private void StartTraining()
    {
        var selectedMaps = _mapsList.CheckedItems.OfType<MapItem>().Select(item => item.Path).ToList();
        if (selectedMaps.Count == 0)
        {
            AppendLog("No maps selected for training.");
            return;
        }

        var args = new List<string>
        {
            "-m", "src.apps.train_osu_lazer_transfer",
            "--updates", ((int)_updates.Value).ToString(),
            "--save-every", ((int)_saveEvery.Value).ToString(),
            "--cursor-speed", _cursorSpeed.Value.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "--learning-rate", _learningRate.Value.ToString(System.Globalization.CultureInfo.InvariantCulture),
            "--maps-dir", _mapsFolder.Text,
        };
        foreach (var map in selectedMaps)
        {
            args.Add("--map");
            args.Add(map);
        }
        if (_resetBest.Checked)
        {
            args.Add("--reset-best");
        }

        _training.Start("training", "python", args, StudioPaths.ProjectRoot);
    }

    private void ExportCheckpoint(string checkpoint)
    {
        if (!File.Exists(checkpoint))
        {
            AppendLog($"Checkpoint not found: {checkpoint}");
            return;
        }

        _export.Start(
            "export",
            "python",
            new[] { "-m", "src.apps.export_osu_policy_onnx", "--checkpoint", checkpoint, "--out", StudioPaths.OnnxOutput },
            StudioPaths.ProjectRoot);
    }

    private void BrowseMapsFolder()
    {
        using var dialog = new FolderBrowserDialog
        {
            SelectedPath = Directory.Exists(_mapsFolder.Text) ? _mapsFolder.Text : StudioPaths.MapsDir,
            Description = "Choose folder with .osu beatmaps",
            UseDescriptionForTitle = true,
        };
        if (dialog.ShowDialog(this) == DialogResult.OK)
        {
            _mapsFolder.Text = dialog.SelectedPath;
            RefreshMaps();
            SaveUiState();
        }
    }

    private void RefreshMaps()
    {
        var selectedPaths = GetSelectedMapPaths();
        _mapsList.Items.Clear();
        var root = _mapsFolder.Text;
        if (!Directory.Exists(root))
        {
            SetMapsStatus($"Maps folder not found: {root}", Red);
            AppendLog($"Maps folder not found: {root}");
            return;
        }

        foreach (var path in Directory.EnumerateFiles(root, "*.osu", SearchOption.AllDirectories).OrderBy(Path.GetFileName))
        {
            var item = new MapItem(path);
            var selected = selectedPaths.Contains(path, StringComparer.OrdinalIgnoreCase)
                || (selectedPaths.Count == 0 && IsDefaultTrainingMap(path));
            _mapsList.Items.Add(item, selected);
        }
        UpdateMapsStatus();
        AppendLog($"Maps scanned: {_mapsList.Items.Count}, selected: {_mapsList.CheckedItems.Count}.");
    }

    private void SetMapsStatus(string text, Color color)
    {
        _mapsStatus.Text = text;
        _mapsStatus.ForeColor = color;
    }

    private static bool IsDefaultTrainingMap(string path)
    {
        var name = Path.GetFileNameWithoutExtension(path).ToLowerInvariant();
        var blocked = new[] { "hard", "insane", "expert", "extra", "lunatic", "another", "hyper", "oni", "sample" };
        if (blocked.Any(name.Contains))
        {
            return false;
        }
        return name.Contains("beginner") || name.Contains("easy");
    }

    private void SetAllMaps(bool selected)
    {
        for (var i = 0; i < _mapsList.Items.Count; i++)
        {
            _mapsList.SetItemChecked(i, selected);
        }
        UpdateMapsStatus();
        SaveUiState();
    }

    private void RefreshConfigList()
    {
        var previous = (_configCombo.SelectedItem as ConfigItem)?.Path;
        _configCombo.Items.Clear();
        if (Directory.Exists(StudioPaths.ControllerConfigsDir))
        {
            foreach (var path in Directory.GetFiles(StudioPaths.ControllerConfigsDir, "*.json").OrderBy(Path.GetFileName))
            {
                _configCombo.Items.Add(new ConfigItem(path));
            }
        }

        SelectConfig(previous ?? StudioPaths.AgentConfig);
    }

    private void SelectConfig(string path)
    {
        for (var i = 0; i < _configCombo.Items.Count; i++)
        {
            if (_configCombo.Items[i] is ConfigItem item && string.Equals(item.Path, path, StringComparison.OrdinalIgnoreCase))
            {
                _configCombo.SelectedIndex = i;
                return;
            }
        }
        if (_configCombo.Items.Count > 0) _configCombo.SelectedIndex = 0;
    }

    private string GetSelectedConfigOrDefault() => _configCombo.SelectedItem is ConfigItem item ? item.Path : StudioPaths.AgentConfig;

    private void RefreshStatus()
    {
        RefreshConfigList();
        SetChip(_agentChip, _controller.IsRunning ? "Running" : "Idle");
        SetChip(_trainChip, _training.IsRunning ? "Running" : "Idle");
        SetChip(_exportChip, _export.IsRunning ? "Running" : "Idle");
        RefreshFileStatusOnly();
        AppendLog("Status refreshed.");
    }

    private void WireProcess(ManagedProcess process, Label chip, string label)
    {
        process.OutputReceived += AppendLog;
        process.StatusChanged += value => BeginInvoke(() => SetChip(chip, value.Replace(label, "", StringComparison.OrdinalIgnoreCase).Trim()));
    }

    private void AppendLog(string line)
    {
        if (InvokeRequired)
        {
            BeginInvoke(() => AppendLog(line));
            return;
        }

        _log.SelectionStart = _log.TextLength;
        _log.SelectionColor = line.Contains("error", StringComparison.OrdinalIgnoreCase) ? Color.FromArgb(255, 120, 145) : Color.FromArgb(214, 226, 244);
        _log.AppendText($"[{DateTime.Now:HH:mm:ss}] {line}{Environment.NewLine}");
        _log.ScrollToCaret();
        RefreshFileStatusOnly();
    }

    private void RefreshFileStatusOnly()
    {
        var latest = File.Exists(StudioPaths.LatestCheckpoint) ? File.GetLastWriteTime(StudioPaths.LatestCheckpoint).ToString("HH:mm") : "missing";
        var best = File.Exists(StudioPaths.BestCheckpoint) ? File.GetLastWriteTime(StudioPaths.BestCheckpoint).ToString("HH:mm") : "missing";
        SetChip(_filesChip, $"latest {latest} / best {best}");
    }

    private static void OpenPath(string path)
    {
        if (!Directory.Exists(path) && !File.Exists(path)) Directory.CreateDirectory(path);
        Process.Start(new ProcessStartInfo { FileName = path, UseShellExecute = true });
    }

    private static TableLayoutPanel TwoColumns()
    {
        var grid = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, BackColor = Color.Transparent };
        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        return grid;
    }

    private static TableLayoutPanel Stack(int rows)
    {
        var stack = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, RowCount = rows, ColumnCount = 1, BackColor = Color.Transparent };
        for (var i = 0; i < rows; i++) stack.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        return stack;
    }

    private static RoundedPanel Card(string title, string subtitle, Color accent, Control content)
    {
        var card = new RoundedPanel { Dock = DockStyle.Fill, Radius = 16, BackColor = Surface, Padding = new Padding(20), Margin = new Padding(0, 0, 14, 0), Accent = accent };
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 3, ColumnCount = 1, BackColor = Color.Transparent };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 40));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        card.Controls.Add(layout);
        layout.Controls.Add(new Label
        {
            Text = title,
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 18f),
            TextAlign = ContentAlignment.MiddleLeft,
            Margin = new Padding(0),
        }, 0, 0);
        layout.Controls.Add(new Label
        {
            Text = subtitle,
            Dock = DockStyle.Fill,
            ForeColor = TextMuted,
            AutoEllipsis = true,
            TextAlign = ContentAlignment.TopLeft,
            Margin = new Padding(0, 0, 0, 8),
        }, 0, 1);

        var contentHost = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            BackColor = Color.Transparent,
            Padding = new Padding(0),
            Margin = new Padding(0),
        };
        content.Dock = DockStyle.Top;
        contentHost.Controls.Add(content);
        layout.Controls.Add(contentHost, 0, 2);
        return card;
    }

    private static Control TextBlock(string text) => new Label
    {
        Text = text,
        Dock = DockStyle.Fill,
        ForeColor = TextMuted,
        Font = new Font("Segoe UI", 11f),
        Padding = new Padding(4),
    };

    private static Control Field(string label, Control input)
    {
        var wrap = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 1, BackColor = Color.Transparent, Margin = new Padding(0, 4, 0, 4) };
        wrap.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 122));
        wrap.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        wrap.Controls.Add(new Label { Text = label, Dock = DockStyle.Fill, ForeColor = TextMuted, TextAlign = ContentAlignment.MiddleLeft }, 0, 0);
        input.Dock = DockStyle.Fill;
        wrap.Controls.Add(input, 1, 0);
        return wrap;
    }

    private static Button Button(string text, Color color, EventHandler handler, Color? fore = null)
    {
        var button = new Button
        {
            Text = text,
            Dock = DockStyle.Fill,
            FlatStyle = FlatStyle.Flat,
            BackColor = color,
            ForeColor = fore ?? Color.FromArgb(4, 8, 14),
            Font = new Font("Segoe UI Semibold", 10.5f),
            Margin = new Padding(0, 5, 8, 5),
            Cursor = Cursors.Hand,
        };
        button.FlatAppearance.BorderSize = 0;
        button.Click += handler;
        return button;
    }

    private Button NavButton(string text, Color accent, Action handler)
    {
        var button = new Button
        {
            Text = text,
            Width = 112,
            Height = 34,
            FlatStyle = FlatStyle.Flat,
            BackColor = Surface,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 9.5f),
            Margin = new Padding(4, 0, 4, 0),
            Cursor = Cursors.Hand,
        };
        button.FlatAppearance.BorderSize = 1;
        button.FlatAppearance.BorderColor = Stroke;
        button.Click += (_, _) => handler();
        _tabButtons.Add(button);
        return button;
    }

    private void ShowTab(Func<Control> playBuilder, int index)
    {
        _currentTabIndex = index;
        _tabContent.Controls.Clear();
        var control = playBuilder();
        control.Dock = DockStyle.Fill;
        _tabContent.Controls.Add(control);

        for (var i = 0; i < _tabButtons.Count; i++)
        {
            var active = i == index;
            _tabButtons[i].BackColor = active ? Surface2 : Surface;
            _tabButtons[i].ForeColor = active ? TextMain : TextMuted;
            _tabButtons[i].FlatAppearance.BorderColor = active ? Cyan : Stroke;
        }

        SaveUiState();
    }

    private void ShowTabByIndex(int index)
    {
        index = Math.Clamp(index, 0, 3);
        switch (index)
        {
            case 0:
                ShowTab(BuildPlayTab, 0);
                break;
            case 1:
                ShowTab(BuildTrainingTab, 1);
                break;
            case 2:
                ShowTab(BuildExportTab, 2);
                break;
            default:
                ShowTab(BuildFilesTab, 3);
                break;
        }
    }

    private void HookStatePersistence()
    {
        _configCombo.SelectedIndexChanged += (_, _) => SaveUiState();
        _mapsFolder.TextChanged += (_, _) => SaveUiState();
        _updates.ValueChanged += (_, _) => SaveUiState();
        _saveEvery.ValueChanged += (_, _) => SaveUiState();
        _cursorSpeed.ValueChanged += (_, _) => SaveUiState();
        _learningRate.ValueChanged += (_, _) => SaveUiState();
        _resetBest.CheckedChanged += (_, _) => SaveUiState();
        _mapsList.ItemCheck += (_, _) =>
        {
            void PersistSelection()
            {
                UpdateMapsStatus();
                SaveUiState();
            }

            if (IsHandleCreated)
            {
                BeginInvoke((Action)PersistSelection);
                return;
            }

            PersistSelection();
        };
        Move += (_, _) => SaveUiState();
        ResizeEnd += (_, _) => SaveUiState();
        SizeChanged += (_, _) => SaveUiState();
    }

    private void ApplyWindowState()
    {
        _restoringState = true;
        try
        {
            if (_state.WindowWidth >= MinimumSize.Width && _state.WindowHeight >= MinimumSize.Height)
            {
                StartPosition = FormStartPosition.Manual;
                Bounds = new Rectangle(
                    _state.WindowX,
                    _state.WindowY,
                    _state.WindowWidth,
                    _state.WindowHeight);
            }

            WindowState = _state.WindowMaximized ? FormWindowState.Maximized : FormWindowState.Normal;
        }
        finally
        {
            _restoringState = false;
        }
    }

    private void ActivateWindowOnLaunch()
    {
        if (!Visible)
        {
            Show();
        }

        if (_state.WindowMaximized && WindowState != FormWindowState.Maximized)
        {
            WindowState = FormWindowState.Maximized;
        }

        Activate();
        BringToFront();
        TopMost = true;
        TopMost = false;
        Focus();
    }

    private void SaveUiState()
    {
        if (_restoringState || !IsHandleCreated)
        {
            return;
        }

        var bounds = WindowState == FormWindowState.Normal ? Bounds : RestoreBounds;
        _state.WindowX = bounds.X;
        _state.WindowY = bounds.Y;
        _state.WindowWidth = bounds.Width;
        _state.WindowHeight = bounds.Height;
        _state.WindowMaximized = WindowState == FormWindowState.Maximized;
        _state.MapsFolder = _mapsFolder.Text;
        _state.Updates = (int)_updates.Value;
        _state.SaveEvery = (int)_saveEvery.Value;
        _state.CursorSpeed = _cursorSpeed.Value;
        _state.LearningRate = _learningRate.Value;
        _state.ResetBest = _resetBest.Checked;
        _state.SelectedConfigPath = GetSelectedConfigOrDefault();
        _state.SelectedTabIndex = _currentTabIndex;
        _state.SelectedMaps = GetSelectedMapPaths();
        StudioStateStore.Save(_state);
    }

    private List<string> GetSelectedMapPaths()
        => _mapsList.CheckedItems
            .OfType<MapItem>()
            .Select(item => item.Path)
            .ToList();

    private void UpdateMapsStatus()
    {
        SetMapsStatus(
            $"Maps scanned: {_mapsList.Items.Count}. Selected: {_mapsList.CheckedItems.Count}.",
            _mapsList.Items.Count > 0 ? TextMuted : Yellow);
    }

    private static Control MakeChip(string title, Label value, Color color)
    {
        var chip = new RoundedPanel { Width = 138, Height = 52, Radius = 13, BackColor = Surface, Accent = color, Padding = new Padding(12, 4, 8, 4), Margin = new Padding(8, 0, 0, 8) };
        var layout = new TableLayoutPanel { Dock = DockStyle.Fill, RowCount = 2, ColumnCount = 1, BackColor = Color.Transparent };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 20));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        chip.Controls.Add(layout);
        layout.Controls.Add(new Label { Text = title, Dock = DockStyle.Fill, ForeColor = color, Font = new Font("Segoe UI Semibold", 8.5f) }, 0, 0);
        value.Dock = DockStyle.Fill;
        value.ForeColor = TextMain;
        value.AutoEllipsis = true;
        SetChip(value, "Idle");
        layout.Controls.Add(value, 0, 1);
        return chip;
    }

    private static void SetChip(Label label, string text) => label.Text = string.IsNullOrWhiteSpace(text) ? "Idle" : text;

    private static void ConfigureNumber(NumericUpDown control, decimal min, decimal max, decimal value, int decimals)
    {
        control.Minimum = min;
        control.Maximum = max;
        control.Value = Math.Clamp(value, min, max);
        control.DecimalPlaces = decimals;
        control.Increment = decimals == 0 ? 1 : 0.00001m;
        control.BackColor = Surface2;
        control.ForeColor = TextMain;
        control.BorderStyle = BorderStyle.FixedSingle;
    }

    private static void StyleCombo(ComboBox combo)
    {
        combo.BackColor = Surface2;
        combo.ForeColor = TextMain;
        combo.FlatStyle = FlatStyle.Flat;
    }

    private static void StyleText(TextBox text)
    {
        text.BackColor = Surface2;
        text.ForeColor = TextMain;
        text.BorderStyle = BorderStyle.FixedSingle;
    }

    private sealed record ConfigItem(string Path)
    {
        public override string ToString() => System.IO.Path.GetFileName(Path);
    }

    private sealed record MapItem(string Path)
    {
        public override string ToString()
        {
            var parent = Directory.GetParent(Path)?.Name ?? "";
            return $"{parent} / {System.IO.Path.GetFileName(Path)}";
        }
    }

    private class RoundedPanel : Panel
    {
        public int Radius { get; set; } = 12;
        public Color Accent { get; set; } = Color.Transparent;

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            using var path = RoundedRect(ClientRectangle, Radius);
            using var brush = new SolidBrush(BackColor);
            e.Graphics.FillPath(brush, path);
            if (Accent != Color.Transparent)
            {
                using var accentBrush = new SolidBrush(Accent);
                e.Graphics.FillRectangle(accentBrush, 0, 18, 4, Math.Max(22, Height - 36));
            }
        }
    }

    private static GraphicsPath RoundedRect(Rectangle bounds, int radius)
    {
        var path = new GraphicsPath();
        var diameter = radius * 2;
        var rect = new Rectangle(bounds.Location, new Size(diameter, diameter));
        path.AddArc(rect, 180, 90);
        rect.X = bounds.Right - diameter;
        path.AddArc(rect, 270, 90);
        rect.Y = bounds.Bottom - diameter;
        path.AddArc(rect, 0, 90);
        rect.X = bounds.Left;
        path.AddArc(rect, 90, 90);
        path.CloseFigure();
        return path;
    }
}
