using System.Diagnostics;
using System.Drawing.Drawing2D;
using System.Reflection;

using System.Runtime.InteropServices;

using System.Collections.Concurrent;
using OsuAgentStudio.Core;

namespace OsuAgentStudio;

public sealed class MainForm : Form
{
    private readonly StudioState _state;
    private readonly ManagedProcess _controller = new();
    private readonly ManagedProcess _training = new();
    private readonly ManagedProcess _export = new();

    private readonly TextBox _log = new();
    private readonly Queue<string> _visibleLogLines = new();
    private const int MaxVisibleLogLines = 800;

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
    private readonly Panel _mainContent = new();
    private readonly Dictionary<string, Button> _shellNavButtons = new();
    private readonly System.Windows.Forms.Timer _ambientTimer = new();
    private Label? _clockLabel;

    private WelcomeOverlayPanel? _welcomePanel;

    private bool _welcomeDismissed;
    private bool _trainingControlsInitialized;
    private bool _restoringState;
    private int _currentTabIndex;
    
    private bool _isClosing;

    private static readonly Color Back = Color.FromArgb(7, 9, 18);
    private static readonly Color Surface = Color.FromArgb(17, 20, 34);
    private static readonly Color Surface2 = Color.FromArgb(23, 27, 44);
    private static readonly Color Surface3 = Color.FromArgb(28, 32, 52);
    private static readonly Color Stroke = Color.FromArgb(42, 48, 74);
    private static readonly Color StrokeSoft = Color.FromArgb(30, 35, 56);

    private static readonly Color TextMain = Color.FromArgb(244, 247, 255);
    private static readonly Color TextMuted = Color.FromArgb(153, 162, 195);
    private static readonly Color TextDim = Color.FromArgb(105, 115, 150);

    private static readonly Color Cyan = Color.FromArgb(87, 202, 255);
    private static readonly Color Pink = Color.FromArgb(224, 74, 209);
    private static readonly Color Purple = Color.FromArgb(162, 64, 255);
    private static readonly Color PurpleDark = Color.FromArgb(48, 24, 82);
    private static readonly Color Magenta = Color.FromArgb(243, 69, 195);
    private static readonly Color Yellow = Color.FromArgb(255, 205, 75);
    private static readonly Color Blue = Color.FromArgb(115, 128, 255);
    private static readonly Color Green = Color.FromArgb(91, 235, 151);
    private static readonly Color Red = Color.FromArgb(255, 86, 122);

    private readonly ConcurrentQueue<string> _pendingLogLines = new();
    private readonly System.Windows.Forms.Timer _logFlushTimer = new();

    private bool _autoScrollConsole = true;

    private const int EM_GETFIRSTVISIBLELINE = 0xCE;
    private const int EM_LINESCROLL = 0xB6;
    public MainForm()
    {
        _state = StudioStateStore.Load();
        StudioStateStore.Save(_state);
        var asm = Assembly.GetExecutingAssembly().GetName();
        Text = asm.Version is { } v ? $"LiraAi  v{FormatVersion(v)}" : "LiraAi";
        FormBorderStyle = FormBorderStyle.Sizable;
        MinimumSize = new Size(1180, 760);
        Size = new Size(_state.WindowWidth, _state.WindowHeight);
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Back;
        Font = new Font("Segoe UI", 10f);
        DoubleBuffered = true;

        var iconPath = Path.Combine(AppContext.BaseDirectory, "app.ico");
        if (File.Exists(iconPath))
        {
            Icon = new Icon(iconPath);
        }

        _mapsFolder.Text = string.IsNullOrWhiteSpace(_state.MapsFolder) ? StudioPaths.MapsDir : _state.MapsFolder;

        WireProcess(_controller, _agentChip, "Agent");
        WireProcess(_training, _trainChip, "Training");
        WireProcess(_export, _exportChip, "Export");

        BuildUi();
        SetupLogQueue();
        HookStatePersistence();
        RefreshConfigList();
        RefreshMaps();
        RefreshStatus();
        ApplyWindowState();
        ShowTabByIndex(Math.Clamp(_state.SelectedTabIndex, 0, 3));
        if (!StudioPaths.IsTrainingFromSourceAvailable())
        {
            AppendLog("Test build: project src/ is not next to the app. Training and ONNX export (Python) are disabled. Launch Agent still works if controller + config + model are on disk.");
        }

        Shown += (_, _) => ActivateWindowOnLaunch();
    }

    [DllImport("user32.dll")]
    private static extern IntPtr SendMessage(IntPtr hWnd, int msg, IntPtr wParam, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool ReleaseCapture();

    private const int WM_NCLBUTTONDOWN = 0xA1;
    private const int HTCAPTION = 0x2;
    private const int WM_NCHITTEST = 0x84;
    private const int HTLEFT = 10;
    private const int HTRIGHT = 11;
    private const int HTTOP = 12;
    private const int HTTOPLEFT = 13;
    private const int HTTOPRIGHT = 14;
    private const int HTBOTTOM = 15;
    private const int HTBOTTOMLEFT = 16;
    private const int HTBOTTOMRIGHT = 17;

    protected override void WndProc(ref Message m)
    {
        if (m.Msg == WM_NCHITTEST && WindowState == FormWindowState.Normal)
        {
            base.WndProc(ref m);
            var cursor = PointToClient(Cursor.Position);
            const int grip = 8;
            var left = cursor.X <= grip;
            var right = cursor.X >= ClientSize.Width - grip;
            var top = cursor.Y <= grip;
            var bottom = cursor.Y >= ClientSize.Height - grip;
            if (left && top) { m.Result = new IntPtr(HTTOPLEFT); return; }
            if (right && top) { m.Result = new IntPtr(HTTOPRIGHT); return; }
            if (left && bottom) { m.Result = new IntPtr(HTBOTTOMLEFT); return; }
            if (right && bottom) { m.Result = new IntPtr(HTBOTTOMRIGHT); return; }
            if (left) { m.Result = new IntPtr(HTLEFT); return; }
            if (right) { m.Result = new IntPtr(HTRIGHT); return; }
            if (top) { m.Result = new IntPtr(HTTOP); return; }
            if (bottom) { m.Result = new IntPtr(HTBOTTOM); return; }
            return;
        }

        base.WndProc(ref m);
    }

    private int GetFirstVisibleLine()
    {
        if (_log.IsDisposed || !_log.IsHandleCreated)
            return 0;

        return SendMessage(_log.Handle, EM_GETFIRSTVISIBLELINE, IntPtr.Zero, IntPtr.Zero).ToInt32();
    }

    private void SetFirstVisibleLine(int targetLine)
    {
        if (_log.IsDisposed || !_log.IsHandleCreated)
            return;

        var currentLine = GetFirstVisibleLine();
        var delta = targetLine - currentLine;

        if (delta != 0)
        {
            SendMessage(_log.Handle, EM_LINESCROLL, IntPtr.Zero, new IntPtr(delta));
        }
    }

    private void SetupLogQueue()
    {
        _logFlushTimer.Interval = 200;
        _logFlushTimer.Tick += (_, _) => FlushPendingLogs();
        _logFlushTimer.Start();
    }

    protected override void OnFormClosing(FormClosingEventArgs e)
    {
        _isClosing = true;

        try { _logFlushTimer.Stop(); } catch { }
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
        root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        root.RowStyles.Add(new RowStyle(SizeType.Absolute, 220));
        Controls.Add(root);

        root.Controls.Add(BuildTopBar(), 0, 0);
        root.Controls.Add(BuildTabs(), 0, 1);
        root.Controls.Add(BuildConsole(), 0, 2);
    }

    private Control BuildShellTitleBar()
    {
        var bar = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 3,
            RowCount = 1,
            BackColor = Color.FromArgb(10, 12, 22),
            Padding = new Padding(28, 14, 28, 14),
        };

        bar.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 420));
        bar.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        bar.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 255));

        bar.MouseDown += (_, e) => BeginWindowDrag(e);

        var brand = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = Color.Transparent,
            Margin = new Padding(0),
            Padding = new Padding(0),
        };

        brand.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 64));
        brand.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        var ringHost = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 10, 14, 10),
        };

        var ring = Picture(Asset("Blocks", "Head_Block", "Logo_Ellipse.png"), PictureBoxSizeMode.Zoom);
        ring.Dock = DockStyle.Fill;
        ringHost.Controls.Add(ring);
        brand.Controls.Add(ringHost, 0, 0);

        var text = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 2,
            ColumnCount = 1,
            BackColor = Color.Transparent,
            Margin = new Padding(0),
            Padding = new Padding(0),
        };

        text.RowStyles.Add(new RowStyle(SizeType.Percent, 58));
        text.RowStyles.Add(new RowStyle(SizeType.Percent, 42));

        text.Controls.Add(new Label
        {
            Text = "DIGITAL COMPANION",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 16f),
            TextAlign = ContentAlignment.BottomLeft,
            AutoEllipsis = true,
            Margin = new Padding(0),
        }, 0, 0);

        text.Controls.Add(new Label
        {
            Text = $"ver. {DisplayVersion()}    dev build",
            Dock = DockStyle.Fill,
            ForeColor = Purple,
            Font = new Font("Segoe UI Semibold", 9.5f),
            TextAlign = ContentAlignment.TopLeft,
            AutoEllipsis = true,
            Margin = new Padding(0),
        }, 0, 1);

        brand.Controls.Add(text, 1, 0);

        bar.Controls.Add(brand, 0, 0);

        var status = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = Color.Transparent,
            Margin = new Padding(0),
            Padding = new Padding(0),
        };

        status.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        status.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));

        var statusText = new Label
        {
            Text = "STATUS\nthinking...",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 9.5f),
            TextAlign = ContentAlignment.TopRight,
            AutoEllipsis = true,
            Margin = new Padding(0, 16, 10, 0),
        };

        status.Controls.Add(statusText, 0, 0);

        var thinkingHost = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 22, 0, 30),
        };

        var thinking = Picture(Asset("Blocks", "Head_Block", "Thinking_Image.png"), PictureBoxSizeMode.Zoom);
        thinking.Dock = DockStyle.Fill;
        thinkingHost.Controls.Add(thinking);

        status.Controls.Add(thinkingHost, 1, 0);
        bar.Controls.Add(status, 1, 0);

        var chrome = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 10, 0, 0),
            Margin = new Padding(0),
        };

        chrome.Controls.Add(IconButton("вљ™", (_, _) => ShowSoon("Parameters")));
        chrome.Controls.Add(IconButton("в€’", (_, _) => WindowState = FormWindowState.Minimized));
        chrome.Controls.Add(IconButton("в–Ў", (_, _) => ToggleMaximize()));
        chrome.Controls.Add(IconButton("Г—", (_, _) => Close()));

        bar.Controls.Add(chrome, 2, 0);

        return bar;
    }

    private Control BuildShellBody()
    {
        var body = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = Back,
            Padding = new Padding(18, 10, 18, 10),
        };

        body.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 276));
        body.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        body.Controls.Add(BuildNavigationRail(), 0, 0);

        _mainContent.Dock = DockStyle.Fill;
        _mainContent.BackColor = Color.Transparent;
        body.Controls.Add(_mainContent, 1, 0);

        return body;
    }

    private Control BuildShellFooter()
    {
        var footer = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 8,
            BackColor = Color.FromArgb(9, 11, 20),
            Padding = new Padding(28, 7, 28, 6),
        };
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 92));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 116));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 168));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 180));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 110));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 160));
        footer.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 86));
        footer.Controls.Add(FooterLabel("SYSTEM", Purple, true), 0, 0);
        footer.Controls.Add(FooterLabel("CPU   12%", TextMuted), 1, 0);
        footer.Controls.Add(FooterLabel("RAM   4.1/16 GB", TextMuted), 2, 0);
        footer.Controls.Add(FooterLabel("VRAM   1.2/8 GB", TextMuted), 3, 0);
        footer.Controls.Add(FooterLabel("MODE     chatting", TextMain), 5, 0);
        _clockLabel = FooterLabel($"UPTIME   {DateTime.Now:HH:mm:ss}", TextMain);
        footer.Controls.Add(_clockLabel, 6, 0);
        footer.Controls.Add(FooterLabel("FPS   60", TextMain), 7, 0);
        return footer;
    }

    private Control BuildNavigationRail()
    {
        var rail = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 3,
            ColumnCount = 1,
            BackColor = Color.Transparent,
        };
        rail.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        rail.RowStyles.Add(new RowStyle(SizeType.Absolute, 150));
        rail.RowStyles.Add(new RowStyle(SizeType.Absolute, 0));

        var navCard = new RoundedPanel
        {
            Dock = DockStyle.Fill,
            Radius = 18,
            BackColor = Color.FromArgb(14, 17, 30),
            Padding = new Padding(14, 18, 14, 16),
            Margin = new Padding(0, 0, 14, 12),
            BorderColor = Color.FromArgb(31, 36, 58),
        };
        var nav = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, ColumnCount = 1, BackColor = Color.Transparent };
        navCard.Controls.Add(nav);
        nav.Controls.Add(new Label
        {
            Text = "NAVIGATION",
            Height = 34,
            Dock = DockStyle.Top,
            ForeColor = Purple,
            Font = new Font("Segoe UI Semibold", 10f),
            Padding = new Padding(12, 4, 0, 0),
        });

        AddShellNav(nav, "chat", "рџ’¬", "Chat", () => ShowShellPage("chat"));
        AddShellNav(nav, "memory", "в—Њ", "Memory", () => ShowSoon("Memory"));
        AddShellNav(nav, "emotion", "в™Ў", "Emotion", () => ShowSoon("Emotion"));
        AddShellNav(nav, "skills", "в†", "Skills", () => ShowSoon("Skills"));
        AddShellNav(nav, "osu", "osu!", "osu! Agent", () => ShowShellPage("osu"));
        AddShellNav(nav, "vision", "в—‰", "Vision", () => ShowSoon("Vision"));
        AddShellNav(nav, "voice", "в‰‹", "Voice", () => ShowSoon("Voice"));
        AddShellNav(nav, "autonomy", "в–Ј", "Autonomy", () => ShowSoon("Autonomy"));
        AddShellNav(nav, "developer", "</>", "Developer", () => ShowSoon("Developer"));
        rail.Controls.Add(navCard, 0, 0);

        var profile = new RoundedPanel
        {
            Dock = DockStyle.Fill,
            Radius = 18,
            BackColor = Color.FromArgb(17, 20, 34),
            Padding = new Padding(16),
            Margin = new Padding(0, 0, 14, 0),
            BorderColor = Color.FromArgb(31, 36, 58),
        };
        var profileGrid = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, RowCount = 2, BackColor = Color.Transparent };
        profileGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 78));
        profileGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        profileGrid.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        profileGrid.RowStyles.Add(new RowStyle(SizeType.Absolute, 26));
        var avatar = Picture(Asset("Avatar.png"), PictureBoxSizeMode.Zoom);
        avatar.Margin = new Padding(0, 4, 12, 10);
        profileGrid.Controls.Add(avatar, 0, 0);
        var nameBlock = new Label
        {
            Text = $"LiraAi\nDigital Companion\nv{DisplayVersion()}",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 11.5f),
            TextAlign = ContentAlignment.MiddleLeft,
        };
        profileGrid.Controls.Add(nameBlock, 1, 0);
        profileGrid.Controls.Add(new Label
        {
            Text = "в—Џ online",
            Dock = DockStyle.Fill,
            ForeColor = Green,
            Font = new Font("Segoe UI", 9f),
            TextAlign = ContentAlignment.MiddleLeft,
        }, 0, 1);
        profile.Controls.Add(profileGrid);
        rail.Controls.Add(profile, 0, 1);
        return rail;
    }

    private void AddShellNav(TableLayoutPanel nav, string key, string icon, string text, Action action)
    {
        var button = new Button
        {
            Text = $"{icon}   {text}",
            Height = 48,
            Dock = DockStyle.Top,
            FlatStyle = FlatStyle.Flat,
            BackColor = Color.Transparent,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 10.5f),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(14, 0, 0, 0),
            Margin = new Padding(0, 3, 0, 3),
            Cursor = Cursors.Hand,
        };
        button.FlatAppearance.BorderSize = 1;
        button.FlatAppearance.BorderColor = Color.FromArgb(14, 17, 30);
        button.Click += (_, _) => action();
        _shellNavButtons[key] = button;
        nav.Controls.Add(button);
    }

    private void ShowShellPage(string key)
    {
        foreach (var pair in _shellNavButtons)
        {
            var active = pair.Key == key;
            pair.Value.BackColor = active ? Color.FromArgb(49, 27, 83) : Color.Transparent;
            pair.Value.ForeColor = active ? TextMain : Color.FromArgb(205, 211, 232);
            pair.Value.FlatAppearance.BorderColor = active ? Purple : Color.FromArgb(14, 17, 30);
        }

        _mainContent.Controls.Clear();
        Control page = key switch
        {
            "chat" => BuildChatPage(),
            "osu" => BuildAgentStudioPage(),
            _ => BuildSoonPage(key),
        };
        page.Dock = DockStyle.Fill;
        _mainContent.Controls.Add(page);
    }

    private Control BuildAgentStudioPage()
    {
        var page = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 3,
            ColumnCount = 1,
            BackColor = Color.Transparent,
        };
        page.RowStyles.Add(new RowStyle(SizeType.Absolute, 76));
        page.RowStyles.Add(new RowStyle(SizeType.Percent, 55));
        page.RowStyles.Add(new RowStyle(SizeType.Percent, 45));
        page.Controls.Add(BuildAgentTopStrip(), 0, 0);
        page.Controls.Add(BuildTabs(), 0, 1);
        page.Controls.Add(BuildConsole(), 0, 2);
        return page;
    }

    private Control BuildAgentTopStrip()
    {
        var top = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 2, BackColor = Color.Transparent };
        top.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        top.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 600));

        var nav = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 20, 0, 0),
        };
        if (_tabButtons.Count == 0)
        {
            nav.Controls.Add(NavButton("Play", Cyan, () => ShowTab(BuildPlayTab, 0)));
            nav.Controls.Add(NavButton("Training", Pink, () => ShowTab(BuildTrainingTab, 1)));
            nav.Controls.Add(NavButton("Export", Yellow, () => ShowTab(BuildExportTab, 2)));
            nav.Controls.Add(NavButton("Files", Blue, () => ShowTab(BuildFilesTab, 3)));
        }
        else
        {
            foreach (var button in _tabButtons)
                nav.Controls.Add(button);
        }
        top.Controls.Add(nav, 0, 0);

        var chips = new FlowLayoutPanel
        {
            Dock = DockStyle.Fill,
            FlowDirection = FlowDirection.LeftToRight,
            WrapContents = false,
            BackColor = Color.Transparent,
            Padding = new Padding(0, 10, 0, 0),
        };
        if (_agentChip.Parent is null) chips.Controls.Add(MakeChip("Agent", _agentChip, Cyan));
        if (_trainChip.Parent is null) chips.Controls.Add(MakeChip("Training", _trainChip, Pink));
        if (_exportChip.Parent is null) chips.Controls.Add(MakeChip("Export", _exportChip, Yellow));
        if (_filesChip.Parent is null) chips.Controls.Add(MakeChip("Files", _filesChip, Green));
        top.Controls.Add(chips, 1, 0);
        return top;
    }

    private Control BuildChatPage()
    {
        var grid = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = Color.Transparent,
            Padding = new Padding(0),
        };

        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        grid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 500));

        var statePanel = BuildStatePanel();
        statePanel.Margin = new Padding(16, 0, 0, 0);

        var chatSurface = BuildChatSurface();
        grid.Controls.Add(chatSurface, 0, 0);
        grid.Controls.Add(statePanel, 1, 0);

        void LayoutChatColumns()
        {
            if (grid.Width <= 0)
                return;

            var compact = grid.Width < 1020;
            statePanel.Visible = !compact;

            if (compact)
            {
                grid.ColumnStyles[1].Width = 0;
                chatSurface.Margin = new Padding(0);
                return;
            }

            var stateWidth = Math.Clamp((int)(grid.Width * 0.32f), 360, 500);
            grid.ColumnStyles[1].Width = stateWidth;
            chatSurface.Margin = new Padding(0, 0, 16, 0);
        }

        grid.Resize += (_, _) => LayoutChatColumns();
        grid.HandleCreated += (_, _) => LayoutChatColumns();

        return grid;
    }

    private Control BuildChatSurface()
    {
        var card = new RoundedPanel
        {
            Dock = DockStyle.Fill,
            Radius = 10,
            BackColor = Color.FromArgb(13, 16, 29),
            Padding = new Padding(0),
            Margin = new Padding(0, 0, 16, 0),
            BorderColor = Color.FromArgb(18, 22, 38)
        };

        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 3,
            ColumnCount = 1,
            BackColor = Color.Transparent
        };

        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 62));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 118));

        card.Controls.Add(layout);

        var header = new RoundedPanel
        {
            Dock = DockStyle.Fill,
            Radius = 12,
            BackColor = Color.FromArgb(22, 26, 42),
            BorderColor = Color.FromArgb(18, 22, 38),
            Padding = new Padding(28, 0, 28, 0),
            Margin = new Padding(0, 0, 0, 0),
        };

        header.Controls.Add(new Label
        {
            Text = "CHAT",
            Dock = DockStyle.Fill,
            ForeColor = Purple,
            Font = new Font("Segoe UI Semibold", 13.5f),
            TextAlign = ContentAlignment.MiddleLeft,
            Padding = new Padding(0, 0, 0, 2)
        });

        layout.Controls.Add(header, 0, 0);

        var messages = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(20, 10, 20, 10),
            AutoScroll = true
        };

        layout.Controls.Add(messages, 0, 1);

        var inputHost = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(16, 8, 16, 20),
            Margin = new Padding(0),
        };

        var input = new RoundedPanel
        {
            Dock = DockStyle.Fill,
            Radius = 18,
            BackColor = Color.FromArgb(23, 27, 42),
            Padding = new Padding(24, 12, 10, 12),
            Margin = new Padding(0),
            BorderColor = Color.FromArgb(190, 196, 215)
        };

        inputHost.Controls.Add(input);

        var inputGrid = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 4,
            RowCount = 1,
            BackColor = Color.Transparent,
            Margin = new Padding(0),
            Padding = new Padding(0)
        };

        inputGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        inputGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 192));
        inputGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 44));
        inputGrid.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 44));

        var prompt = new TextBox
        {
            PlaceholderText = "РќР°РїРёС€Рё С‡С‚Рѕ-РЅРёР±СѓРґСЊ...",
            Dock = DockStyle.Fill,
            BorderStyle = BorderStyle.None,
            BackColor = Color.FromArgb(23, 27, 42),
            ForeColor = TextDim,
            Font = new Font("Segoe UI Semibold", 12f),
            Margin = new Padding(0, 12, 16, 0)
        };

        inputGrid.Controls.Add(prompt, 0, 0);
        inputGrid.Controls.Add(ChatSendButton(), 1, 0);
        inputGrid.Controls.Add(ChatIconButton("рџЋ™", () => ShowSoon("Voice input")), 2, 0);
        inputGrid.Controls.Add(ChatIconButton("в·", () => ShowSoon("Chat preferences")), 3, 0);

        input.Controls.Add(inputGrid);

        void LayoutInput()
        {
            var narrow = input.Width < 640;
            input.Padding = narrow ? new Padding(16, 10, 8, 10) : new Padding(24, 12, 10, 12);
            inputGrid.ColumnStyles[1].Width = narrow ? 54 : 192;

            if (inputGrid.GetControlFromPosition(1, 0) is Control send)
            {
                send.Text = narrow ? "вћ¤" : "РћС‚РїСЂР°РІРёС‚СЊ  вћ¤";
                if (send.Controls.Count > 0 && send.Controls[0] is Label label)
                    label.Text = send.Text;
            }
        }

        input.Resize += (_, _) => LayoutInput();
        input.HandleCreated += (_, _) => LayoutInput();

        layout.Controls.Add(inputHost, 0, 2);

        return card;
    }

    private Control ChatSendButton()
    {
        var button = new RoundedPanel
        {
            Text = "РћС‚РїСЂР°РІРёС‚СЊ  вћ¤",
            Dock = DockStyle.Fill,
            BackColor = Purple,
            Radius = 18,
            BorderColor = Color.Transparent,
            Margin = new Padding(0, 4, 8, 4),
            Cursor = Cursors.Hand,
        };

        var label = new Label
        {
            Text = button.Text,
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = Color.White,
            Font = new Font("Segoe UI Semibold", 11f),
            TextAlign = ContentAlignment.MiddleCenter,
            Cursor = Cursors.Hand,
        };

        void Click(object? sender, EventArgs args) => ShowSoon("Chat");
        button.Click += Click;
        label.Click += Click;
        button.Controls.Add(label);

        return button;
    }

    private Control ChatIconButton(string text, Action action)
    {
        var button = new RoundedPanel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.FromArgb(34, 38, 56),
            Radius = 17,
            BorderColor = Color.Transparent,
            Margin = new Padding(0, 5, 6, 5),
            Cursor = Cursors.Hand,
        };

        var label = new Label
        {
            Text = text,
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 14f),
            TextAlign = ContentAlignment.MiddleCenter,
            Cursor = Cursors.Hand,
        };

        void Click(object? sender, EventArgs args) => action();
        button.Click += Click;
        label.Click += Click;
        button.Controls.Add(label);

        return button;
    }

    private Control ChatBubble(string author, string text, string time, bool mine, int x, int y)
    {
        var bubble = new RoundedPanel
        {
            Width = mine ? 180 : 440,
            Height = mine ? 78 : 126,
            Radius = 16,
            BackColor = mine ? Color.FromArgb(71, 27, 124) : Color.FromArgb(25, 29, 45),
            BorderColor = mine ? Color.FromArgb(91, 42, 150) : StrokeSoft,
            Padding = new Padding(16),
            Location = new Point(x, y)
        };

        var label = new Label
        {
            Text = $"{author}\n{text}\n{time}",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI", 10.5f),
            TextAlign = ContentAlignment.MiddleLeft
        };

        label.ForeColor = mine ? Color.FromArgb(238, 230, 255) : TextMain;
        bubble.Controls.Add(label);

        return bubble;
    }

    private Control BuildStatePanel()
    {
        var panel = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 3,
            ColumnCount = 1,
            BackColor = Color.Transparent,
            Padding = new Padding(0),
            Margin = new Padding(0),
        };

        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 380));
        panel.RowStyles.Add(new RowStyle(SizeType.Absolute, 210));
        panel.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        panel.Controls.Add(Card("STATE", "", Purple, BuildMoodBlock()), 0, 0);
        panel.Controls.Add(Card("ACTIVE SKILLS", "", Purple, BuildSkillsBlock()), 0, 1);
        panel.Controls.Add(Card("LAST EVENTS", "", Purple, BuildEventsBlock()), 0, 2);

        return panel;
    }

    private Control BuildMoodBlock()
    {
        var body = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 6,
            ColumnCount = 1,
            BackColor = Color.Transparent,
            Padding = new Padding(0),
            Margin = new Padding(0),
        };

        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 74));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));

        var mood = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            BackColor = Color.Transparent,
            Margin = new Padding(0),
            Padding = new Padding(0),
        };

        mood.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 78));
        mood.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));

        var moodIconHost = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(8, 0, 12, 8),
        };

        moodIconHost.Controls.Add(Picture(
            Asset("Blocks", "State_Block", "Mood_State_Block", "Playfull_Mood_Image.png"),
            PictureBoxSizeMode.Zoom
        ));

        mood.Controls.Add(moodIconHost, 0, 0);

        mood.Controls.Add(new Label
        {
            Text = "playful\nР›С‘РіРєРѕРµ РЅР°СЃС‚СЂРѕРµРЅРёРµ, РіРѕС‚РѕРІР° Рє С€СѓС‚РєР°Рј.",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 10.5f),
            TextAlign = ContentAlignment.MiddleLeft,
            AutoEllipsis = true,
        }, 1, 0);

        body.Controls.Add(mood, 0, 0);
        body.Controls.Add(Bar("Energy", 72, Purple), 0, 1);
        body.Controls.Add(Bar("Curiosity", 88, Purple), 0, 2);
        body.Controls.Add(Bar("Irritation", 12, Yellow), 0, 3);
        body.Controls.Add(TagRow("playful", "banter"), 0, 4);
        body.Controls.Add(TagRow("sarcasm в†‘", "warmth в†’", "teasing в†‘"), 0, 5);

        return body;
    }

    private Control BuildEventsBlock()
    {
        return TextBlock("23:40   РўС‹ Р·Р°РїСѓСЃС‚РёР» osu!\n23:38   LiraAi РїРѕС€СѓС‚РёР»Р° РїСЂРѕ С‚РІРѕР№ РїР»РµР№СЃС‚Р°Р№Р»\n23:35   РўС‹ СЃРїСЂРѕСЃРёР» РїСЂРѕ СѓСЃС‚Р°РІ");
    }

    private Control BuildSoonPage(string key)
    {
        return Card(key.ToUpperInvariant(), "This module is a polished placeholder for now.", Purple,
            new Label
            {
                Text = "РЎРєРѕСЂРѕ Р·РґРµСЃСЊ РїРѕСЏРІРёС‚СЃСЏ РѕС‚РґРµР»СЊРЅС‹Р№ СЌРєСЂР°РЅ.",
                Dock = DockStyle.Fill,
                ForeColor = TextMain,
                Font = new Font("Segoe UI Semibold", 18f),
                TextAlign = ContentAlignment.MiddleCenter,
            });
    }

    private void ShowSoon(string title)
    {
        MessageBox.Show(this, "РЎРєРѕСЂРѕ.", title, MessageBoxButtons.OK, MessageBoxIcon.Information);
    }

    private static Label FooterLabel(string text, Color color, bool strong = false) => new()
    {
        Text = text,
        Dock = DockStyle.Fill,
        ForeColor = color,
        Font = new Font("Segoe UI Semibold", strong ? 10f : 9.5f),
        TextAlign = ContentAlignment.MiddleLeft,
    };

    private static Button IconButton(string text, EventHandler handler)
    {
        var button = new Button
        {
            Text = text,
            Width = 46,
            Height = 46,
            FlatStyle = FlatStyle.Flat,
            BackColor = Color.FromArgb(25, 29, 46),
            ForeColor = TextMuted,
            Font = new Font("Segoe UI Semibold", 13f),
            Margin = new Padding(7, 0, 0, 0),
            Cursor = Cursors.Hand,
            TextAlign = ContentAlignment.MiddleCenter,
        };

        button.FlatAppearance.BorderSize = 1;
        button.FlatAppearance.BorderColor = Color.FromArgb(34, 40, 64);
        button.Click += handler;

        return button;
    }

    private Button IconOnly(string path, Action action)
    {
        var button = IconButton("", (_, _) => action());
        button.BackgroundImage = File.Exists(path) ? Image.FromFile(path) : null;
        button.BackgroundImageLayout = ImageLayout.Center;
        return button;
    }

    private void BeginWindowDrag(MouseEventArgs e)
    {
        if (e.Button != MouseButtons.Left)
            return;

        ReleaseCapture();
        SendMessage(Handle, WM_NCLBUTTONDOWN, new IntPtr(HTCAPTION), IntPtr.Zero);
    }

    private void ToggleMaximize()
    {
        WindowState = WindowState == FormWindowState.Maximized
            ? FormWindowState.Normal
            : FormWindowState.Maximized;
    }

    private static PictureBox Picture(string path, PictureBoxSizeMode mode)
    {
        var box = new PictureBox
        {
            Dock = DockStyle.Fill,
            SizeMode = mode,
            BackColor = Color.Transparent,
            Margin = new Padding(0),
        };

        try
        {
            if (File.Exists(path))
            {
                using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                box.Image = Image.FromStream(fs);
            }
            else
            {
                box.BackColor = Color.FromArgb(20, 10, 30);
            }
        }
        catch
        {
            box.BackColor = Color.FromArgb(40, 10, 30);
        }

        return box;
    }

    private static Control Bar(string label, int value, Color color)
    {
        var row = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3, BackColor = Color.Transparent };
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 92));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        row.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 48));
        row.Controls.Add(new Label { Text = label, Dock = DockStyle.Fill, ForeColor = TextMain, TextAlign = ContentAlignment.MiddleLeft }, 0, 0);
        var track = new ProgressBar { Dock = DockStyle.Fill, Value = Math.Clamp(value, 0, 100), Style = ProgressBarStyle.Continuous, Margin = new Padding(0, 16, 14, 16) };
        track.ForeColor = color;
        row.Controls.Add(track, 1, 0);
        row.Controls.Add(new Label { Text = $"{value}%", Dock = DockStyle.Fill, ForeColor = TextMain, TextAlign = ContentAlignment.MiddleRight }, 2, 0);
        return row;
    }

    private static Control TagRow(params string[] tags)
    {
        var row = new FlowLayoutPanel { Dock = DockStyle.Fill, BackColor = Color.Transparent, WrapContents = false };
        foreach (var tag in tags)
        {
            row.Controls.Add(new Label
            {
                Text = tag,
                AutoSize = true,
                ForeColor = Color.FromArgb(219, 175, 255),
                BackColor = Color.FromArgb(36, 29, 61),
                Font = new Font("Segoe UI Semibold", 9f),
                Padding = new Padding(10, 6, 10, 6),
                Margin = new Padding(0, 8, 10, 0),
            });
        }
        return row;
    }

    private Control BuildSkillsBlock()
    {
        var panel = new Panel
        {
            Dock = DockStyle.Fill,
            BackColor = Color.Transparent,
            Padding = new Padding(8, 0, 8, 0),
        };

        var skills = new[]
        {
            ("РџР°РјСЏС‚СЊ",  Asset("Blocks", "State_Block", "ActiveSkills_State_Block", "Memory_Button_Skills.png"),   Color.FromArgb(0x18, 0x1E, 0x36)),
            ("Р­РјРѕС†РёРё",  Asset("Blocks", "State_Block", "ActiveSkills_State_Block", "Emotions_Button_Skills.png"), Color.FromArgb(0xA3, 0x2D, 0x8D)),
            ("Р“Р»Р°Р·Р°",   Asset("Blocks", "State_Block", "ActiveSkills_State_Block", "Vision_Button_Skills.png"),   Color.FromArgb(0x7A, 0xA5, 0xC3)),
            ("Р§Р°С‚",     Asset("Blocks", "State_Block", "ActiveSkills_State_Block", "Chat_Button_Skills.png"),     Color.FromArgb(0xAC, 0xB3, 0xC1)),
        };

        var tiles = skills.Select(s => SkillButton(s.Item1, s.Item2, s.Item3)).ToArray();
        foreach (var tile in tiles)
            panel.Controls.Add(tile);

    void LayoutTiles()
    {
        if (panel.Width <= 0)
            return;

        const int tileW = 84;
        const int tileH = 122;
        const int square = 72;

        const int startX = 0;
        const int gap = 18;

        var x = startX;
        var y = 0;

        foreach (var tile in tiles)
        {
            tile.Size = new Size(tileW, tileH);
            tile.Location = new Point(x, y);

            if (tile.Controls[0] is RoundedPanel squarePanel)
            {
                squarePanel.Size = new Size(square, square);
                squarePanel.Location = new Point((tileW - square) / 2, 0);
            }

            if (tile.Controls[1] is Label label)
            {
                label.Size = new Size(tileW, 26);
                label.Location = new Point(0, square + 6);
                label.TextAlign = ContentAlignment.MiddleCenter;
                label.Visible = true;
                label.BringToFront();
            }

            x += tileW + gap;
        }
    }

        panel.Resize += (_, _) => LayoutTiles();
        panel.HandleCreated += (_, _) => LayoutTiles();

        return panel;
    }

    private static Control SkillButton(string label, string iconPath, Color squareColor)
    {
        var host = new Panel
        {
            BackColor = Color.Transparent,
            Margin = new Padding(0),
            Padding = new Padding(0),
        };

        var square = new RoundedPanel
        {
            Radius = 14,
            BackColor = squareColor,
            BorderColor = Color.FromArgb(55, 62, 92),
            Padding = new Padding(0),
        };

        var icon = new PictureBox
        {
            Size = new Size(56, 56),
            SizeMode = PictureBoxSizeMode.Zoom,
            BackColor = Color.Transparent,
        };

        try
        {
            if (File.Exists(iconPath))
            {
                using var fs = new FileStream(iconPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                icon.Image = Image.FromStream(fs);
            }
        }
        catch { }

        square.Controls.Add(icon);

        square.Resize += (_, _) =>
        {
            icon.Location = new Point(
                (square.Width - icon.Width) / 2,
                (square.Height - icon.Height) / 2
            );
        };

        var text = new Label
        {
            Text = label,
            ForeColor = TextMuted,
            Font = new Font("Segoe UI Semibold", 9f),
            TextAlign = ContentAlignment.MiddleCenter,
            AutoEllipsis = false,
            BackColor = Color.Transparent,
        };

        host.Controls.Add(square);
        host.Controls.Add(text);

        return host;
    }

    private string Asset(params string[] parts)
        => Path.Combine(new[] { AppContext.BaseDirectory, "AppImage" }.Concat(parts).ToArray());

    private static string FormatVersion(Version version)
        => version.Revision == 0
            ? $"{version.Major}.{version.Minor}.{version.Build}"
            : version.ToString();

    private string DisplayVersion()
    {
        var version = Assembly.GetExecutingAssembly().GetName().Version;
        return version is null ? "1.0.3" : FormatVersion(version);
    }

    private void ShowWelcomeOverlay()
    {
        if (_welcomeDismissed || _welcomePanel is not null)
            return;

        var greeting = GetGreeting();

        _welcomePanel = new WelcomeOverlayPanel
        {
            Dock = DockStyle.Fill,
            Title = greeting.Title,
            Subtitle = greeting.Subtitle,
            StatusText = "LiraAi is online",
            StartText = "РќР°С‡Р°С‚СЊ СЂР°Р±РѕС‚Сѓ",
            BackgroundPath = greeting.ImagePath,
            Font = Font,
        };

        _welcomePanel.FadeOutFinished += (_, _) =>
        {
            _welcomeDismissed = true;
            _welcomePanel?.Dispose();
            _welcomePanel = null;
        };

        Controls.Add(_welcomePanel);
        _welcomePanel.BringToFront();
    }

    private void LayoutWelcomeOverlay()
    {
        _welcomePanel?.Invalidate();
    }

    private (string Title, string Subtitle, string ImagePath) GetGreeting()
    {
        var hour = DateTime.Now.Hour;
        if (hour >= 5 && hour < 12)
        {
            return ("Р”РѕР±СЂРѕРµ СѓС‚СЂРѕ", "РњСЏРіРєРёР№ СЃС‚Р°СЂС‚, С‡РёСЃС‚С‹Р№ С„РѕРєСѓСЃ, Рё РјРѕР¶РЅРѕ Р°РєРєСѓСЂР°С‚РЅРѕ СЂР°Р·РіРѕРЅСЏС‚СЊСЃСЏ.", Asset("Hello_Image", "Good_Morning.png"));
        }

        if (hour >= 12 && hour < 18)
        {
            return ("Р”РѕР±СЂС‹Р№ РґРµРЅСЊ", "Р Р°Р±РѕС‡РёР№ СЂРµР¶РёРј РІРєР»СЋС‡РµРЅ. LiraAi СЂСЏРґРѕРј Рё РіРѕС‚РѕРІР° РїРѕРјРѕРіР°С‚СЊ.", Asset("Hello_Image", "Good_Day.png"));
        }

        if (hour >= 18 && hour < 23)
        {
            return ("Р”РѕР±СЂС‹Р№ РІРµС‡РµСЂ", "РњРѕР¶РЅРѕ СЃР±Р°РІРёС‚СЊ С€СѓРј РґРЅСЏ Рё СЃРїРѕРєРѕР№РЅРѕ РїСЂРѕРґРѕР»Р¶РёС‚СЊ СЃ С‚РѕРіРѕ РјРµСЃС‚Р°, РіРґРµ РѕСЃС‚Р°РЅРѕРІРёР»РёСЃСЊ.", Asset("Hello_Image", "Good_Evening.png"));
        }

        return ("Р”РѕР±СЂРѕР№ РЅРѕС‡Рё", "РўРёС…РёР№ СЂРµР¶РёРј. РќРёРєР°РєРѕР№ СЃСѓРµС‚С‹, С‚РѕР»СЊРєРѕ С‚РѕС‡РЅС‹Рµ РґРµР№СЃС‚РІРёСЏ Рё РјСЏРіРєРёР№ РЅРµРѕРЅ.", Asset("Hello_Image", "Good_Night.png"));
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

        top.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        top.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 480));
        top.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 600));

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
        var canTrain = StudioPaths.IsTrainingFromSourceAvailable();
        var settingsSub = canTrain
            ? "Choose maps, set training parameters, then start or stop training."
            : "Test bundle: training disabled without src/apps. Put full repo next to the bundle, or add OSUAGENTSTUDIO_PROJECT_ROOT, to enable Python training.";
        var mapsSub = canTrain
            ? "Beginner/easy maps are selected by default. You can add a folder and choose exactly what goes into training."
            : "Map list is for future training; Launch Agent (Play) works without this in test builds.";

        var scroll = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            BackColor = Color.Transparent
        };

        var host = new RoundedPanel
        {
            Dock = DockStyle.Top,
            AutoSize = true,
            Radius = 16,
            BackColor = Surface,
            Padding = new Padding(20),
            Margin = new Padding(0),
            Accent = Pink,
            BorderColor = Color.FromArgb(31, 36, 58),
        };

        scroll.Controls.Add(host);

        var layout = new TableLayoutPanel { Dock = DockStyle.Top, AutoSize = true, AutoSizeMode = AutoSizeMode.GrowAndShrink, RowCount = 5, ColumnCount = 1, BackColor = Color.Transparent };
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 74));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 236));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 64));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 520));
        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 64));

        host.Controls.Add(layout);

        layout.Controls.Add(new Label
        {
            Text = $"Fine-Tune Settings\n{settingsSub}",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 14f),
            TextAlign = ContentAlignment.MiddleLeft,
        }, 0, 0);
        layout.Controls.Add(BuildTrainingControls(includeActions: false), 0, 1);
        layout.Controls.Add(new Label
        {
            Text = $"Training Maps\n{mapsSub}",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 13f),
            TextAlign = ContentAlignment.MiddleLeft,
        }, 0, 2);
        layout.Controls.Add(BuildMapPicker(includeStartButton: false), 0, 3);

        var actions = new TableLayoutPanel { Dock = DockStyle.Fill, ColumnCount = 3, BackColor = Color.Transparent };
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
        actions.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 25));
        var startTrain = Button("Start Training", Pink, (_, _) => StartTraining());
        startTrain.Enabled = canTrain;
        actions.Controls.Add(startTrain, 0, 0);
        actions.Controls.Add(Button("Stop Training", Red, (_, _) => _training.Stop("training")), 1, 0);
        actions.Controls.Add(Button("Open Checkpoints", Blue, (_, _) => OpenPath(StudioPaths.CheckpointsDir)), 2, 0);
        layout.Controls.Add(actions, 0, 4);
        return scroll;
    }

    private Control BuildExportTab()
    {
        var canExport = StudioPaths.IsExportFromSourceAvailable();
        var exportSub = canExport
            ? "Export a checkpoint into the model used by live play."
            : "Test bundle: export is disabled (no src/apps).";
        var grid = TwoColumns();
        grid.Controls.Add(Card("Export ONNX", exportSub, Yellow, BuildExportControls()), 0, 0);
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
        body.Controls.Add(Button("Open Live Logs", Blue, (_, _) => OpenPath(StudioPaths.ResolveLogsDir())), 0, 4);
        return body;
    }

    private Control BuildRuntimeNotes()
    {
        return TextBlock(
            "Auto map mode resolves the current osu!lazer map after gameplay starts.\n\n" +
            "Pause/stop events are watched from osu!lazer runtime logs, so the controller releases input instead of playing through menus.\n\n" +
            "Sensitivity in osu!lazer should stay at 1.0.");
    }

    private Control BuildTrainingControls(bool includeActions = true)
    {
        var canTrain = StudioPaths.IsTrainingFromSourceAvailable();
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
        if (includeActions)
        {
            var startTrain = Button("Start Training", Pink, (_, _) => StartTraining());
            startTrain.Enabled = canTrain;
            body.Controls.Add(startTrain, 0, 5);
            var stopTrain = Button("Stop Training", Red, (_, _) => _training.Stop("training"));
            body.Controls.Add(stopTrain, 0, 6);
            body.Controls.Add(Button("Open Checkpoints", Blue, (_, _) => OpenPath(StudioPaths.CheckpointsDir)), 0, 7);
        }
        return body;
    }

    private Control BuildMapPicker(bool includeStartButton = true)
    {
        var canTrain = StudioPaths.IsTrainingFromSourceAvailable();
        var body = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = includeStartButton ? 5 : 4,
            ColumnCount = 1,
            BackColor = Color.Transparent
        };
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        body.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        body.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
        if (includeStartButton)
            body.RowStyles.Add(new RowStyle(SizeType.Absolute, 48));
        body.MinimumSize = new Size(0, includeStartButton ? 560 : 500);

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
        _mapsList.ScrollAlwaysVisible = true;
        mapsHost.Controls.Add(_mapsList);
        body.Controls.Add(mapsHost, 0, 2);

        _mapsStatus.Dock = DockStyle.Fill;
        _mapsStatus.ForeColor = TextMuted;
        _mapsStatus.Text = "Selected maps are passed explicitly to training.";
        _mapsStatus.TextAlign = ContentAlignment.MiddleLeft;
        body.Controls.Add(_mapsStatus, 0, 3);
        if (includeStartButton)
        {
            var startMaps = Button("Start Training With Selected Maps", Pink, (_, _) => StartTraining());
            startMaps.Enabled = canTrain;
            body.Controls.Add(startMaps, 0, 4);
        }
        return body;
    }

    private Control BuildExportControls()
    {
        var canExport = StudioPaths.IsExportFromSourceAvailable();
        var body = Stack(7);
        var exLatest = Button("Export Latest", Yellow, (_, _) => ExportCheckpoint(StudioPaths.LatestCheckpoint));
        exLatest.Enabled = canExport;
        var exBest = Button("Export Best", Green, (_, _) => ExportCheckpoint(StudioPaths.BestCheckpoint));
        exBest.Enabled = canExport;
        body.Controls.Add(exLatest, 0, 0);
        body.Controls.Add(exBest, 0, 1);
        body.Controls.Add(Button("Open ONNX Folder", Blue, (_, _) => OpenPath(Path.GetDirectoryName(StudioPaths.OnnxOutput)!)), 0, 2);
        body.Controls.Add(Button("Refresh Status", Cyan, (_, _) => RefreshStatus()), 0, 3);
        return body;
    }

    private Control BuildCheckpointNotes()
    {
        return TextBlock(
            "Use Export Latest when you want to test what is currently learning.\n\n" +
            "Use Export Best when the cycle score actually improved.\n\n" +
            "Export writes to artifacts/exports/onnx/lazer_transfer_generalization.onnx вЂ” the file used by runtime.onnx.live_play.agent_observed.gu.json (Launch Agent).");
    }

    private Control BuildFileButtons()
    {
        var body = Stack(8);
        body.Controls.Add(Button("Open Maps Folder", Cyan, (_, _) => OpenPath(_mapsFolder.Text)), 0, 0);
        body.Controls.Add(Button("Open Checkpoints", Pink, (_, _) => OpenPath(StudioPaths.CheckpointsDir)), 0, 1);
        body.Controls.Add(Button("Open ONNX Folder", Yellow, (_, _) => OpenPath(Path.GetDirectoryName(StudioPaths.OnnxOutput)!)), 0, 2);
        body.Controls.Add(Button("Open Controller Configs", Blue, (_, _) => OpenPath(StudioPaths.ControllerConfigsDir)), 0, 3);
        body.Controls.Add(Button("Open Studio Logs", Green, (_, _) => OpenPath(StudioPaths.StudioLogsDir)), 0, 4);
        return body;
    }

    private Control BuildConsole()
    {
        var card = new RoundedPanel
        {
            Dock = DockStyle.Fill,
            Radius = 16,
            BackColor = Surface,
            Padding = new Padding(16)
        };

        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = 2,
            ColumnCount = 1,
            BackColor = Color.Transparent
        };

        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));
        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
        card.Controls.Add(layout);

        var head = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            ColumnCount = 2,
            RowCount = 1,
            BackColor = Color.Transparent
        };

        head.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
        head.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));

        head.Controls.Add(new Label
        {
            Text = "Console",
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 15f),
            TextAlign = ContentAlignment.MiddleLeft,
        }, 0, 0);

        var clearButton = Button("Clear Console", Surface2, (_, _) =>
        {
            _visibleLogLines.Clear();
            _pendingLogLines.Clear();
            _log.Text = "";
            _autoScrollConsole = true;
        }, TextMain);

        clearButton.Height = 32;
        clearButton.Dock = DockStyle.Fill;
        clearButton.Margin = new Padding(0, 4, 0, 6);

        head.Controls.Add(clearButton, 1, 0);

        layout.Controls.Add(head, 0, 0);

        _log.Dock = DockStyle.Fill;
        _log.BackColor = Color.FromArgb(3, 5, 10);
        _log.ForeColor = Color.FromArgb(214, 226, 244);
        _log.BorderStyle = BorderStyle.None;
        _log.Font = new Font("Cascadia Mono", 9.5f);
        _log.ReadOnly = true;
        _log.Multiline = true;
        _log.ScrollBars = ScrollBars.Vertical;
        _log.WordWrap = false;

        _log.MouseWheel += (_, _) => BeginInvoke(UpdateConsoleAutoScrollState);
        _log.KeyUp += (_, _) => BeginInvoke(UpdateConsoleAutoScrollState);
        _log.MouseUp += (_, _) => BeginInvoke(UpdateConsoleAutoScrollState);

        layout.Controls.Add(_log, 0, 1);

        return card;
    }

    private void UpdateConsoleAutoScrollState()
    {
        if (_log.IsDisposed || !_log.IsHandleCreated)
            return;

        var firstVisible = GetFirstVisibleLine();
        var visibleLines = Math.Max(1, _log.ClientSize.Height / Math.Max(1, _log.Font.Height));
        var totalLines = Math.Max(1, _log.Lines.Length);

        _autoScrollConsole = firstVisible + visibleLines >= totalLines - 2;
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
        if (!StudioPaths.IsTrainingFromSourceAvailable())
        {
            AppendLog("Training is not available in this build (no src/apps). Use full project or set OSUAGENTSTUDIO_PROJECT_ROOT.");
            return;
        }

        var selectedMaps = _mapsList.CheckedItems.OfType<MapItem>().Select(item => item.Path).ToList();
        if (selectedMaps.Count == 0)
        {
            AppendLog("No maps selected for training.");
            return;
        }
       
        var args = new List<string>
        {
            "-m", "src.apps.train_osu_lazer_transfer",
            "--run-name", StudioPaths.PrecisionRunName,
            "--source-checkpoint",
            Path.Combine(
                StudioPaths.ProjectRoot,
                "artifacts", "runs",
                "osu_lazer_transfer_problem_normals_v1",
                "checkpoints",
                "best_lazer_transfer.pt"
            ),
            "--profile", "precision_spinner",
            "--resume-latest",
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

        args.Insert(0, "-u");
        _training.Start("training", "python", args, StudioPaths.ProjectRoot);
    }

    private void ExportCheckpoint(string checkpoint)
    {
        if (!StudioPaths.IsExportFromSourceAvailable())
        {
            AppendLog("ONNX export needs Python project (src/apps/export_osu_policy_onnx). Not in test-only bundle.");
            return;
        }

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
        if (selectedPaths.Count == 0 && _state.SelectedMaps.Count > 0)
        {
            selectedPaths = _state.SelectedMaps
                .Where(File.Exists)
                .ToList();
        }
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

        process.StatusChanged += value =>
        {
            if (_isClosing || IsDisposed || Disposing || !IsHandleCreated)
                return;

            try
            {
                BeginInvoke(() =>
                {
                    if (_isClosing || chip.IsDisposed)
                        return;

                    SetChip(chip, value.Replace(label, "", StringComparison.OrdinalIgnoreCase).Trim());
                });
            }
            catch (ObjectDisposedException) { }
            catch (InvalidOperationException) { }
        };
    }

    private readonly string _logFilePath = StudioPaths.StudioRuntimeLog;

    private void AppendLog(string line)
    {
        if (string.IsNullOrWhiteSpace(line))
            return;

        _pendingLogLines.Enqueue(line);

        try
        {
            Directory.CreateDirectory(Path.GetDirectoryName(_logFilePath)!);
            File.AppendAllText(_logFilePath,
                $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] {line}{Environment.NewLine}");
        }
        catch
        {
            // РјРѕР»С‡Р°, С‡С‚РѕР±С‹ РЅРµ СѓР±РёС‚СЊ РїСЂРёР»РѕР¶РµРЅРёРµ
        }
    }

    private void FlushPendingLogs()
    {
        if (_isClosing || IsDisposed || Disposing || !IsHandleCreated || _log.IsDisposed)
            return;

        try
        {
            var changed = false;

            var processed = 0;

            while (processed < 100 && _pendingLogLines.TryDequeue(out var line))
            {
                _visibleLogLines.Enqueue($"[{DateTime.Now:HH:mm:ss}] {line}");

                while (_visibleLogLines.Count > MaxVisibleLogLines)
                    _visibleLogLines.Dequeue();

                changed = true;
                processed++;
            }

            if (!changed)
                return;

            var wasAutoScroll = _autoScrollConsole;
            var oldFirstVisibleLine = GetFirstVisibleLine();
            var oldSelection = _log.SelectionStart;

            _log.Text = string.Join(Environment.NewLine, _visibleLogLines) + Environment.NewLine;

            if (wasAutoScroll)
            {
                _log.SelectionStart = _log.TextLength;
                _log.ScrollToCaret();
            }
            else
            {
                _log.SelectionStart = Math.Clamp(oldSelection, 0, _log.TextLength);
                SetFirstVisibleLine(oldFirstVisibleLine);
            }

            RefreshFileStatusOnly();
            UpdateConsoleAutoScrollState();
        }
        catch (ObjectDisposedException) { }
        catch (InvalidOperationException) { }
        catch (Exception ex)
        {
            try
            {
                var logDir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                    "OsuAgentStudio");

                Directory.CreateDirectory(logDir);

                File.AppendAllText(
                    Path.Combine(logDir, "studio_ui_log_error.txt"),
                    $"[{DateTime.Now:yyyy-MM-dd HH:mm:ss}] FlushPendingLogs failed:{Environment.NewLine}{ex}{Environment.NewLine}{new string('-', 80)}{Environment.NewLine}");
            }
            catch { }
        }
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

    private sealed class WelcomeOverlayPanel : Panel
    {
        public string Title { get; set; } = "";
        public string Subtitle { get; set; } = "";
        public string StatusText { get; set; } = "";
        public string StartText { get; set; } = "";
        public string BackgroundPath { get; set; } = "";

        public event EventHandler? FadeOutFinished;

        private bool _closing;

        private Image? _background;
        private Rectangle _buttonRect;

        private readonly System.Windows.Forms.Timer _fadeTimer = new();
        private float _fade = 0f;

        public WelcomeOverlayPanel()
        {
            DoubleBuffered = true;
            Cursor = Cursors.Default;

            _fadeTimer.Interval = 16;
            _fadeTimer.Tick += (_, _) =>
            {
                if (_closing)
                {
                    _fade = Math.Max(0f, _fade - 0.055f);
                    Invalidate();

                    if (_fade <= 0f)
                    {
                        _fadeTimer.Stop();
                        FadeOutFinished?.Invoke(this, EventArgs.Empty);
                    }

                    return;
                }

                _fade = Math.Min(1f, _fade + 0.045f);
                Invalidate();

                if (_fade >= 1f)
                    _fadeTimer.Stop();
            };

            _fadeTimer.Start();
        }

        public void BeginClose()
        {
            if (_closing)
                return;

            _closing = true;
            _fadeTimer.Start();
        }

        protected override void OnCreateControl()
        {
            base.OnCreateControl();

            if (_background is null && File.Exists(BackgroundPath))
            {
                using var temp = Image.FromFile(BackgroundPath);
                _background = new Bitmap(temp);
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                _background?.Dispose();
                _background = null;
            }

            base.Dispose(disposing);
        }

        protected override void OnMouseMove(MouseEventArgs e)
        {
            var hover = _buttonRect.Contains(e.Location);
            Cursor = hover ? Cursors.Hand : Cursors.Default;
            Invalidate();
            base.OnMouseMove(e);
        }

        protected override void OnMouseDown(MouseEventArgs e)
        {
            if (e.Button == MouseButtons.Left && _buttonRect.Contains(e.Location))
            {
                BeginClose();
                return;
            }

            base.OnMouseDown(e);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);

            var g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

            if (_background is not null)
            {
                var zoom = 1.04f - 0.04f * _fade;
                var bgW = Width * zoom;
                var bgH = Height * zoom;
                var bgX = (Width - bgW) / 2f;
                var bgY = (Height - bgH) / 2f;

                g.DrawImage(_background, bgX, bgY, bgW, bgH);
            }
            else
            {
                using var bg = new SolidBrush(Color.Black);
                g.FillRectangle(bg, ClientRectangle);
            }

            var dimAlpha = (int)(150 * _fade);
            using (var dim = new SolidBrush(Color.FromArgb(dimAlpha, 0, 0, 0)))
            {
                g.FillRectangle(dim, ClientRectangle);
            }

            var cardW = Math.Min(640, Width - 80);
            var cardH = 300;
            var cardX = (Width - cardW) / 2;
            var cardY = (Height - cardH) / 2;

            var card = new Rectangle(cardX, cardY, cardW, cardH);

            using var titleFont = new Font("Segoe UI Semibold", 30f);
            using var subtitleFont = new Font("Segoe UI", 13f);
            using var statusFont = new Font("Segoe UI Semibold", 13f);
            using var buttonFont = new Font("Segoe UI Semibold", 10.5f);

            
            var textAlpha = (int)(255 * _fade);

            using var titleBrush = new SolidBrush(Color.FromArgb(textAlpha, TextMain));
            using var subtitleBrush = new SolidBrush(Color.FromArgb(textAlpha, 218, 224, 244));
            using var statusBrush = new SolidBrush(Color.FromArgb(textAlpha, Purple));

            var mouse = PointToClient(Cursor.Position);
            var buttonHover = _buttonRect.Contains(mouse);
            var buttonColor = buttonHover
                ? Color.FromArgb(textAlpha, 174, 76, 255)
                : Color.FromArgb(textAlpha, Purple);

            using var buttonBrush = new SolidBrush(buttonColor);

            using var buttonTextBrush = new SolidBrush(Color.FromArgb(textAlpha, Color.White));

            var ease = 1f - MathF.Pow(1f - _fade, 3f);
            var rise = (int)(28 * (1f - ease));

            DrawCenteredText(g, Title, titleFont, titleBrush, new Rectangle(cardX + 24, cardY + 36 + rise, cardW - 48, 48));
            DrawCenteredText(g, Subtitle, subtitleFont, subtitleBrush, new Rectangle(cardX + 34, cardY + 98 + rise, cardW - 68, 44));
            DrawCenteredText(g, StatusText, statusFont, statusBrush, new Rectangle(cardX + 24, cardY + 146 + rise, cardW - 48, 34));

            _buttonRect = new Rectangle(cardX + (cardW - 220) / 2, cardY + 204 + rise, 220, 48);

            using (var buttonPath = RoundedRect(_buttonRect, 4))
            {
                g.FillPath(buttonBrush, buttonPath);
            }

            DrawCenteredText(g, StartText, buttonFont, buttonTextBrush, _buttonRect);
        }

        private static void DrawCenteredText(Graphics g, string text, Font font, Brush brush, Rectangle rect)
        {
            using var format = new StringFormat
            {
                Alignment = StringAlignment.Center,
                LineAlignment = StringAlignment.Center,
                Trimming = StringTrimming.EllipsisWord,
                FormatFlags = StringFormatFlags.NoWrap,
            };

            g.DrawString(text, font, brush, rect, format);
        }
    }

    private static RoundedPanel Card(string title, string subtitle, Color accent, Control content)
    {
        var card = new RoundedPanel
        {
            Dock = DockStyle.Fill,
            Radius = 18,
            BackColor = Surface,
            Padding = new Padding(18, 12, 18, 18),
            Margin = new Padding(0, 0, 0, 14),
            Accent = accent,
            BorderColor = Color.FromArgb(69, 75, 98)
        };

        var layout = new TableLayoutPanel
        {
            Dock = DockStyle.Fill,
            RowCount = string.IsNullOrWhiteSpace(subtitle) ? 2 : 3,
            ColumnCount = 1,
            BackColor = Color.Transparent
        };

        layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));

        if (!string.IsNullOrWhiteSpace(subtitle))
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 42));

        layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));

        card.Controls.Add(layout);

        layout.Controls.Add(new Label
        {
            Text = title,
            Dock = DockStyle.Fill,
            ForeColor = TextMain,
            Font = new Font("Segoe UI Semibold", 18f),
            TextAlign = ContentAlignment.MiddleLeft,
            Margin = new Padding(0, 0, 0, 4),
        }, 0, 0);

        var contentRow = 1;

        if (!string.IsNullOrWhiteSpace(subtitle))
        {
            layout.Controls.Add(new Label
            {
                Text = subtitle,
                Dock = DockStyle.Fill,
                ForeColor = TextMuted,
                AutoEllipsis = true,
                TextAlign = ContentAlignment.TopLeft,
                Margin = new Padding(0, 0, 0, 8),
            }, 0, 1);

            contentRow = 2;
        }

        var contentHost = new Panel
        {
            Dock = DockStyle.Fill,
            AutoScroll = true,
            BackColor = Color.Transparent,
            Padding = new Padding(0),
            Margin = new Padding(0),
        };

        content.Dock = DockStyle.Fill;
        contentHost.Controls.Add(content);
        layout.Controls.Add(contentHost, 0, contentRow);

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

            WindowState = FormWindowState.Maximized;
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
        public Color BorderColor { get; set; } = Color.Transparent;

        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            using var path = RoundedRect(ClientRectangle, Radius);
            using var brush = new SolidBrush(BackColor);
            e.Graphics.FillPath(brush, path);
            if (BorderColor != Color.Transparent)
            {
                using var pen = new Pen(BorderColor, 1f);
                e.Graphics.DrawPath(pen, path);
            }
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
