using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.Reflection;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Threading;
using OsuAgentStudio.Core;

namespace OsuAgentStudio.Avalonia.ViewModels;

public sealed class MainWindowViewModel : ObservableObject
{
    private const int MaxVisibleLogLines = 800;

    private readonly StudioService _studio = new();
    private readonly StudioState _state;
    private ConfigItem? _selectedConfig;
    private int _selectedTabIndex;
    private string _mapsFolder;
    private int _updates;
    private int _saveEvery;
    private decimal _cursorSpeed;
    private decimal _learningRate;
    private bool _resetBest;
    private bool _isInitializing = true;
    private string _currentSection = "Osu";
    private bool _isWelcomeVisible = true;
    private bool _isAgentsMenuOpen;
    private string _agentStatus = "Idle";
    private string _trainingStatus = "Idle";
    private string _exportStatus = "Idle";
    private string _filesStatus = "Idle";
    private string _mapsStatus = "Обучаюсь выбранным карточкам. Скоро на изи их пройду, хи!)";
    private string _agentReactionText = "Я тут! И я, в отличии от некоторых, уже готова к работе! Пошли работаааать, учицааааа!!!";

    public MainWindowViewModel()
    {
        _state = StudioStateStore.Load();
        _mapsFolder = string.IsNullOrWhiteSpace(_state.MapsFolder) ? StudioPaths.MapsDir : _state.MapsFolder;
        _updates = _state.Updates;
        _saveEvery = _state.SaveEvery;
        _cursorSpeed = _state.CursorSpeed;
        _learningRate = _state.LearningRate;
        _resetBest = _state.ResetBest;
        _selectedTabIndex = _state.SelectedTabIndex;

        Title = $"osu! Agent Studio  v{FormatVersion(Assembly.GetExecutingAssembly().GetName().Version)}";

        LaunchAgentCommand = new RelayCommand(() => _studio.StartController(SelectedConfig?.Path ?? StudioPaths.AgentConfig));
        LaunchOracleCommand = new RelayCommand(() => _studio.StartController(StudioPaths.OracleConfig));
        StopAgentCommand = new RelayCommand(_studio.StopControllerProcesses);
        OpenLiveLogsCommand = new RelayCommand(() => _studio.OpenPath(StudioPaths.ResolveLogsDir()));
        RescanMapsCommand = new RelayCommand(RefreshMaps);
        SelectAllMapsCommand = new RelayCommand(() => SetAllMaps(true));
        SelectNoneMapsCommand = new RelayCommand(() => SetAllMaps(false));
        StartTrainingCommand = new RelayCommand(StartTraining);
        StopTrainingCommand = new RelayCommand(_studio.StopTraining);
        OpenCheckpointsCommand = new RelayCommand(() => _studio.OpenPath(StudioPaths.CheckpointsDir));
        ExportLatestCommand = new RelayCommand(() => _studio.ExportCheckpoint(StudioPaths.LatestCheckpoint));
        ExportBestCommand = new RelayCommand(() => _studio.ExportCheckpoint(StudioPaths.ExportBestCheckpoint));
        OpenOnnxFolderCommand = new RelayCommand(() => _studio.OpenPath(Path.GetDirectoryName(StudioPaths.OnnxOutput)!));
        RefreshStatusCommand = new RelayCommand(RefreshStatus);
        OpenMapsFolderCommand = new RelayCommand(() => _studio.OpenPath(MapsFolder));
        OpenConfigsCommand = new RelayCommand(() => _studio.OpenPath(StudioPaths.ControllerConfigsDir));
        OpenStudioLogsCommand = new RelayCommand(() => _studio.OpenPath(StudioPaths.StudioLogsDir));
        ClearConsoleCommand = new RelayCommand(Logs.Clear);
        StartWorkCommand = new RelayCommand(() => IsWelcomeVisible = false);
        NavigateChatCommand = new RelayCommand(() => Navigate("Chat"));
        NavigateMemoryCommand = new RelayCommand(() => Navigate("Memory"));
        NavigateEmotionCommand = new RelayCommand(() => Navigate("Emotion"));
        NavigateSkillsCommand = new RelayCommand(() => Navigate("Skills"));
        NavigateAgentsCommand = new RelayCommand(() => IsAgentsMenuOpen = !IsAgentsMenuOpen);
        NavigateVisionCommand = new RelayCommand(() => Navigate("Vision"));
        NavigateVoiceCommand = new RelayCommand(() => Navigate("Voice"));
        NavigateAutonomyCommand = new RelayCommand(() => Navigate("Autonomy"));
        NavigateDevCommand = new RelayCommand(() => Navigate("Dev"));
        NavigateOsuCommand = new RelayCommand(() => Navigate("Osu"));
        NavigateMinecraftCommand = new RelayCommand(() => Navigate("Minecraft"));

        Maps.CollectionChanged += MapsChanged;
        _studio.LogReceived += line => Dispatcher.UIThread.Post(() => AppendLog(line));
        _studio.StatusChanged += (key, value) => Dispatcher.UIThread.Post(() => SetProcessStatus(key, value));

        RefreshConfigList();
        RefreshMaps();
        RefreshStatus();
        _isInitializing = false;
        SaveState();

        if (!StudioPaths.IsTrainingFromSourceAvailable())
            AppendLog("Test build: project src/ is not next to the app. Training and ONNX export (Python) are disabled. Launch Agent still works if controller + config + model are on disk.");
    }

    public string Title { get; }
    public string AppName => "DIGITAL LIRA AI";
    public string CharacterName => "LiraAi";
    public string AppVersion => FormatVersion(Assembly.GetExecutingAssembly().GetName().Version);
    public string VersionText => $"ver. {AppVersion}";
    public string ShellStatus => IsOsuAgentVisible ? "osu agent online" : IsChatVisible ? "thinking..." : "module standby";
    public string ModuleTitle => IsOsuAgentVisible ? "OSU AGENT" : IsChatVisible ? "CHAT" : CurrentSection.ToUpperInvariant();
    public string PlaceholderText => $"{CurrentSection} скоро появится. Сейчас этот модуль подключен как заглушка.";
    public string AgentModuleText => IsAgentsMenuOpen ? "Agents" : "Agents";
    public Bitmap? AvatarImage { get; } = LoadAssetBitmap("AppImage/Avatar.png");
    public Bitmap? LogoEllipseImage { get; } = LoadAssetBitmap("AppImage/Blocks/Head_Block/Logo_Ellipse.png");
    public Bitmap? ParametersImage { get; } = LoadAssetBitmap("AppImage/Blocks/Head_Block/Parametres.png");
    public Bitmap? ThinkingImage { get; } = LoadAssetBitmap("AppImage/Blocks/Head_Block/Thinking_Image.png");
    public Bitmap? SendImage { get; } = LoadAssetBitmap("AppImage/Blocks/Send_Message_Block/Send Button.png");
    public Bitmap? MicroImage { get; } = LoadAssetBitmap("AppImage/Blocks/Send_Message_Block/Micro.png");
    public Bitmap? PreferencesImage { get; } = LoadAssetBitmap("AppImage/Blocks/Send_Message_Block/Preferences.png");
    public Bitmap? MoodImage { get; } = LoadAssetBitmap("AppImage/Blocks/State_Block/Mood_State_Block/Playfull_Mood_Image.png");
    public Bitmap? NavChatIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Chat_Button_Nav.png");
    public Bitmap? NavMemoryIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Memory_Button_Nav.png");
    public Bitmap? NavEmotionIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Emotion_Button_Nav.png");
    public Bitmap? NavSkillsIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Skills_Button_Nav.png");
    public Bitmap? NavAgentsIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Agents_Button_Nav.png");
    public Bitmap? NavVisionIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Vision_Button_Nav.png");
    public Bitmap? NavVoiceIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Voice_Button_Nav.png");
    public Bitmap? NavAutonomyIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Autonomy_Button_Nav.png");
    public Bitmap? NavDevIcon { get; } = LoadAssetBitmap("AppImage/Blocks/Navigation_Block/Dev_Button_Nav.png");
    public Bitmap? SkillChatIcon { get; } = LoadAssetBitmap("AppImage/Blocks/State_Block/ActiveSkills_State_Block/Chat_Button_Skills.png");
    public Bitmap? SkillMemoryIcon { get; } = LoadAssetBitmap("AppImage/Blocks/State_Block/ActiveSkills_State_Block/Memory_Button_Skills.png");
    public Bitmap? SkillEmotionIcon { get; } = LoadAssetBitmap("AppImage/Blocks/State_Block/ActiveSkills_State_Block/Emotions_Button_Skills.png");
    public Bitmap? SkillVisionIcon { get; } = LoadAssetBitmap("AppImage/Blocks/State_Block/ActiveSkills_State_Block/Vision_Button_Skills.png");
    public Bitmap? WelcomeBackgroundImage { get; } = LoadWelcomeBitmap();
    public string WelcomeTitle { get; } = GetWelcomeTitle();
    public string WelcomeText { get; } = GetWelcomeText();
    public bool IsTrainingAvailable => StudioPaths.IsTrainingFromSourceAvailable();
    public bool IsExportAvailable => StudioPaths.IsExportFromSourceAvailable();
    public bool IsOsuAgentVisible => CurrentSection == "Osu";
    public bool IsChatVisible => CurrentSection == "Chat";
    public bool IsPlaceholderVisible => !IsOsuAgentVisible && !IsChatVisible;
    public ObservableCollection<LogLineViewModel> Logs { get; } = [];
    public ObservableCollection<ConfigItem> Configs { get; } = [];
    public ObservableCollection<MapItemViewModel> Maps { get; } = [];

    public RelayCommand LaunchAgentCommand { get; }
    public RelayCommand LaunchOracleCommand { get; }
    public RelayCommand StopAgentCommand { get; }
    public RelayCommand OpenLiveLogsCommand { get; }
    public RelayCommand RescanMapsCommand { get; }
    public RelayCommand SelectAllMapsCommand { get; }
    public RelayCommand SelectNoneMapsCommand { get; }
    public RelayCommand StartTrainingCommand { get; }
    public RelayCommand StopTrainingCommand { get; }
    public RelayCommand OpenCheckpointsCommand { get; }
    public RelayCommand ExportLatestCommand { get; }
    public RelayCommand ExportBestCommand { get; }
    public RelayCommand OpenOnnxFolderCommand { get; }
    public RelayCommand RefreshStatusCommand { get; }
    public RelayCommand OpenMapsFolderCommand { get; }
    public RelayCommand OpenConfigsCommand { get; }
    public RelayCommand OpenStudioLogsCommand { get; }
    public RelayCommand ClearConsoleCommand { get; }
    public RelayCommand StartWorkCommand { get; }
    public RelayCommand NavigateChatCommand { get; }
    public RelayCommand NavigateMemoryCommand { get; }
    public RelayCommand NavigateEmotionCommand { get; }
    public RelayCommand NavigateSkillsCommand { get; }
    public RelayCommand NavigateAgentsCommand { get; }
    public RelayCommand NavigateVisionCommand { get; }
    public RelayCommand NavigateVoiceCommand { get; }
    public RelayCommand NavigateAutonomyCommand { get; }
    public RelayCommand NavigateDevCommand { get; }
    public RelayCommand NavigateOsuCommand { get; }
    public RelayCommand NavigateMinecraftCommand { get; }

    public string CurrentSection
    {
        get => _currentSection;
        private set
        {
            if (SetProperty(ref _currentSection, value))
            {
                OnPropertyChanged(nameof(IsOsuAgentVisible));
                OnPropertyChanged(nameof(IsChatVisible));
                OnPropertyChanged(nameof(IsPlaceholderVisible));
                OnPropertyChanged(nameof(ModuleTitle));
                OnPropertyChanged(nameof(PlaceholderText));
                OnPropertyChanged(nameof(ShellStatus));
            }
        }
    }

    public bool IsWelcomeVisible
    {
        get => _isWelcomeVisible;
        set => SetProperty(ref _isWelcomeVisible, value);
    }

    public bool IsAgentsMenuOpen
    {
        get => _isAgentsMenuOpen;
        private set => SetProperty(ref _isAgentsMenuOpen, value);
    }

    public ConfigItem? SelectedConfig
    {
        get => _selectedConfig;
        set
        {
            if (SetProperty(ref _selectedConfig, value))
                SaveState();
        }
    }

    public int SelectedTabIndex
    {
        get => _selectedTabIndex;
        set
        {
            if (SetProperty(ref _selectedTabIndex, Math.Clamp(value, 0, 3)))
                SaveState();
        }
    }

    public string MapsFolder
    {
        get => _mapsFolder;
        set
        {
            if (SetProperty(ref _mapsFolder, value))
                SaveState();
        }
    }

    public int Updates
    {
        get => _updates;
        set
        {
            if (SetProperty(ref _updates, Math.Clamp(value, 1, 100000)))
                SaveState();
        }
    }

    public int SaveEvery
    {
        get => _saveEvery;
        set
        {
            if (SetProperty(ref _saveEvery, Math.Clamp(value, 10, 1000)))
                SaveState();
        }
    }

    public decimal CursorSpeed
    {
        get => _cursorSpeed;
        set
        {
            if (SetProperty(ref _cursorSpeed, Math.Clamp(value, 5m, 40m)))
                SaveState();
        }
    }

    public decimal LearningRate
    {
        get => _learningRate;
        set
        {
            if (SetProperty(ref _learningRate, Math.Clamp(value, 0.000003m, 0.01m)))
                SaveState();
        }
    }

    public bool ResetBest
    {
        get => _resetBest;
        set
        {
            if (SetProperty(ref _resetBest, value))
                SaveState();
        }
    }

    public string AgentStatus
    {
        get => _agentStatus;
        private set => SetProperty(ref _agentStatus, string.IsNullOrWhiteSpace(value) ? "Idle" : value);
    }

    public string TrainingStatus
    {
        get => _trainingStatus;
        private set => SetProperty(ref _trainingStatus, string.IsNullOrWhiteSpace(value) ? "Idle" : value);
    }

    public string ExportStatus
    {
        get => _exportStatus;
        private set => SetProperty(ref _exportStatus, string.IsNullOrWhiteSpace(value) ? "Idle" : value);
    }

    public string FilesStatus
    {
        get => _filesStatus;
        private set => SetProperty(ref _filesStatus, value);
    }

    public string MapsStatus
    {
        get => _mapsStatus;
        private set => SetProperty(ref _mapsStatus, value);
    }

    public string AgentReactionText
    {
        get => _agentReactionText;
        private set => SetProperty(ref _agentReactionText, value);
    }

    public void SetMapsFolder(string folder)
    {
        MapsFolder = folder;
        RefreshMaps();
    }

    public void SaveWindowState(double x, double y, double width, double height, bool maximized)
    {
        if (x > -10000 && y > -10000)
        {
            _state.WindowX = (int)x;
            _state.WindowY = (int)y;
        }

        if (!maximized)
        {
            _state.WindowWidth = (int)width;
            _state.WindowHeight = (int)height;
        }

        _state.WindowMaximized = maximized;
        SaveState();
    }

    public void SaveNow() => SaveState();

    public StudioState GetState() => _state;

    public void Shutdown()
    {
        SaveState();
        _studio.Shutdown();
    }

    private void RefreshConfigList()
    {
        var previous = SelectedConfig?.Path ?? _state.SelectedConfigPath;
        Configs.Clear();
        foreach (var config in _studio.RefreshConfigList())
            Configs.Add(config);

        SelectedConfig = Configs.FirstOrDefault(item => string.Equals(item.Path, previous, StringComparison.OrdinalIgnoreCase))
            ?? Configs.FirstOrDefault(item => string.Equals(item.Path, StudioPaths.AgentConfig, StringComparison.OrdinalIgnoreCase))
            ?? Configs.FirstOrDefault();
    }

    private void RefreshMaps()
    {
        var selected = Maps.Count > 0
            ? Maps.Where(item => item.IsSelected).Select(item => item.Path).ToList()
            : _state.SelectedMaps;

        Maps.CollectionChanged -= MapsChanged;
        Maps.Clear();
        foreach (var map in _studio.ScanMaps(MapsFolder, selected))
        {
            var vm = new MapItemViewModel(map, OnMapSelectionChanged);
            Maps.Add(vm);
        }
        Maps.CollectionChanged += MapsChanged;

        UpdateMapsStatus();
        SaveState();
    }

    private void SetAllMaps(bool selected)
    {
        foreach (var map in Maps)
            map.IsSelected = selected;

        UpdateMapsStatus();
        SaveState();
    }

    private void StartTraining()
    {
        var selectedMaps = Maps.Where(item => item.IsSelected).Select(item => item.Path).ToList();
        _studio.StartTraining(new TrainingOptions(
            Updates,
            SaveEvery,
            CursorSpeed,
            LearningRate,
            ResetBest,
            MapsFolder,
            selectedMaps));
    }

    private void RefreshStatus()
    {
        RefreshConfigList();
        AgentStatus = _studio.IsControllerRunning ? "Running" : "Idle";
        TrainingStatus = _studio.IsTrainingRunning ? "Running" : "Idle";
        ExportStatus = _studio.IsExportRunning ? "Running" : "Idle";
        UpdateAgentReaction("status");
        RefreshFileStatusOnly();
        AppendLog("Status refreshed.");
    }

    private void RefreshFileStatusOnly()
    {
        var status = _studio.GetFileStatus();
        FilesStatus = $"latest {status.LatestCheckpoint} / best {status.BestCheckpoint}";
    }

    private void SetProcessStatus(string key, string value)
    {
        switch (key)
        {
            case "agent":
                AgentStatus = value;
                break;
            case "training":
                TrainingStatus = value;
                break;
            case "export":
                ExportStatus = value;
                break;
        }

        RefreshFileStatusOnly();
        UpdateAgentReaction(key);
    }

    private void AppendLog(string line)
    {
        Logs.Add(CreateLogLine($"[{DateTime.Now:HH:mm:ss}] {line}", line));
        while (Logs.Count > MaxVisibleLogLines)
            Logs.RemoveAt(0);

        UpdateAgentReactionFromLog(line);
        RefreshFileStatusOnly();
    }

    private static LogLineViewModel CreateLogLine(string text, string source)
    {
        var lower = source.ToLowerInvariant();
        var kind = "info";
        IBrush brush = new SolidColorBrush(Color.Parse("#EEF3FF"));

        if (lower.Contains("error") || lower.Contains("failed") || lower.Contains("exception") || lower.Contains("not found"))
        {
            kind = "error";
            brush = new SolidColorBrush(Color.Parse("#FF6A82"));
        }
        else if (lower.Contains("stopped") || lower.Contains("killed") || lower.Contains("stop"))
        {
            kind = "stop";
        }
        else if (lower.Contains("export"))
        {
            kind = "export";
        }
        else if (lower.Contains("reward=") || lower.Contains("[update"))
        {
            kind = "reward";
        }
        else if (lower.Contains("[training]") || lower.Contains("training"))
        {
            kind = "training";
        }
        else if (lower.Contains("[agent]") || lower.Contains("controller") || lower.Contains("oracle"))
        {
            kind = "agent";
        }
        else if (lower.Contains("maps"))
        {
            kind = "maps";
        }

        var (prefix, reward, between, miss, suffix) = SplitMetricSegments(text);
        return new LogLineViewModel(text, brush, kind, prefix, reward, between, miss, suffix);
    }

    private static (string Prefix, string Reward, string Between, string Miss, string Suffix) SplitMetricSegments(string text)
    {
        var rewardIndex = text.IndexOf("reward=", StringComparison.OrdinalIgnoreCase);
        var missIndex = text.IndexOf("miss=", StringComparison.OrdinalIgnoreCase);

        if (rewardIndex < 0 && missIndex < 0)
            return (text, string.Empty, string.Empty, string.Empty, string.Empty);

        if (rewardIndex >= 0 && (missIndex < 0 || rewardIndex < missIndex))
        {
            var rewardEnd = FindMetricEnd(text, rewardIndex);
            var prefix = text[..rewardIndex];
            var reward = text[rewardIndex..rewardEnd];

            if (missIndex >= rewardEnd)
            {
                var missEnd = FindMetricEnd(text, missIndex);
                return (
                    prefix,
                    reward,
                    text[rewardEnd..missIndex],
                    text[missIndex..missEnd],
                    text[missEnd..]);
            }

            return (prefix, reward, text[rewardEnd..], string.Empty, string.Empty);
        }

        var end = FindMetricEnd(text, missIndex);
        return (text[..missIndex], string.Empty, string.Empty, text[missIndex..end], text[end..]);
    }

    private static int FindMetricEnd(string text, int start)
    {
        var index = start;
        while (index < text.Length && !char.IsWhiteSpace(text[index]))
            index++;

        while (index < text.Length && char.IsWhiteSpace(text[index]))
            index++;

        while (index < text.Length && !char.IsWhiteSpace(text[index]))
            index++;

        return Math.Clamp(index, start, text.Length);
    }

    private void UpdateAgentReaction(string source)
    {
        if (TrainingStatus.Equals("Running", StringComparison.OrdinalIgnoreCase))
            AgentReactionText = "Ура, тренируемся, и едим вкусности! (Или неть... 🤔)";
        else if (ExportStatus.Equals("Running", StringComparison.OrdinalIgnoreCase))
            AgentReactionText = "Экспортирую модель… аккуратно, это важно.";
        else if (AgentStatus.Equals("Running", StringComparison.OrdinalIgnoreCase))
            AgentReactionText = "Я в игре! Записываем в журнальчик что происходит!";
        else if (source == "agent")
            AgentReactionText = "Состояние изменилось. Я готова.";
        else
            AgentReactionText = "Я тут! И я в отличии от некоторых готова учица!";
    }

    private void UpdateAgentReactionFromLog(string line)
    {
        var lower = line.ToLowerInvariant();
        if (lower.Contains("reward="))
            AgentReactionText = "Хороший сигнал. Пожираем все вкусняшки что только можно! Становимся лучше!";
        else if (lower.Contains("miss="))
            AgentReactionText = "Эх... Много промахов... Но я уже исправлюясь. (";
        else if (lower.Contains("latest saved"))
            AgentReactionText = "Сохраняем последний чекпоинт. Это пригодится потом.";
        else if (lower.Contains("started"))
            UpdateAgentReaction("status");
    }

    private void UpdateMapsStatus() =>
        MapsStatus = $"Maps scanned: {Maps.Count}. Selected: {Maps.Count(item => item.IsSelected)}.";

    private void OnMapSelectionChanged()
    {
        UpdateMapsStatus();
        SaveState();
    }

    private void MapsChanged(object? sender, NotifyCollectionChangedEventArgs e) => UpdateMapsStatus();

    private void SaveState()
    {
        if (_isInitializing)
            return;

        _state.MapsFolder = MapsFolder;
        _state.Updates = Updates;
        _state.SaveEvery = SaveEvery;
        _state.CursorSpeed = CursorSpeed;
        _state.LearningRate = LearningRate;
        _state.ResetBest = ResetBest;
        _state.SelectedConfigPath = SelectedConfig?.Path ?? StudioPaths.AgentConfig;
        _state.SelectedTabIndex = SelectedTabIndex;
        _state.SelectedMaps = Maps.Where(item => item.IsSelected).Select(item => item.Path).ToList();
        StudioStateStore.Save(_state);
    }

    private static string FormatVersion(Version? version) =>
        version is null ? "dev" : $"{version.Major}.{version.Minor}.{version.Build}";

    private void Navigate(string section)
    {
        CurrentSection = section;
        IsAgentsMenuOpen = false;
    }

    private static Bitmap? LoadAssetBitmap(string relativePath)
    {
        var path = Path.Combine(AppContext.BaseDirectory, relativePath.Replace('/', Path.DirectorySeparatorChar));
        return File.Exists(path) ? new Bitmap(path) : null;
    }

    private static Bitmap? LoadWelcomeBitmap()
    {
        var hour = DateTime.Now.Hour;
        var fileName = hour switch
        {
            >= 5 and < 12 => "Good_Morning.png",
            >= 12 and < 18 => "Good_Day.png",
            >= 18 and < 23 => "Good_Evening.png",
            _ => "Good_Night.png"
        };

        return LoadAssetBitmap($"AppImage/Hello_Image/{fileName}");
    }

    private static string GetWelcomeTitle()
    {
        var hour = DateTime.Now.Hour;
        return hour switch
        {
            >= 5 and < 12 => "Доброе утро.",
            >= 12 and < 18 => "Добрый день.",
            >= 18 and < 23 => "Добрый вечер.",
            _ => "Доброй ночи."
        };
    }

    private static string GetWelcomeText()
    {
        var hour = DateTime.Now.Hour;
        return hour switch
        {
            >= 5 and < 12 => "LiraAi в сети. Давай работать :)",
            >= 12 and < 18 => "Рабочее пространство готово. OSU Agent уже ждёт.",
            >= 18 and < 23 => "Свет приглушён, оболочка тёплая, и все готово к вечерней работе.",
            _ => "Ночной режим включён. Хи."
        };
    }
}
