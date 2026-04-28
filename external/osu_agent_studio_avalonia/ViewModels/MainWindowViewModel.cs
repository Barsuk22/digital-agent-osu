using System.Collections.ObjectModel;
using System.Collections.Specialized;
using System.Reflection;
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
    private string _agentStatus = "Idle";
    private string _trainingStatus = "Idle";
    private string _exportStatus = "Idle";
    private string _filesStatus = "Idle";
    private string _mapsStatus = "Selected maps are passed explicitly to training.";

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
        ExportBestCommand = new RelayCommand(() => _studio.ExportCheckpoint(StudioPaths.BestCheckpoint));
        OpenOnnxFolderCommand = new RelayCommand(() => _studio.OpenPath(Path.GetDirectoryName(StudioPaths.OnnxOutput)!));
        RefreshStatusCommand = new RelayCommand(RefreshStatus);
        OpenMapsFolderCommand = new RelayCommand(() => _studio.OpenPath(MapsFolder));
        OpenConfigsCommand = new RelayCommand(() => _studio.OpenPath(StudioPaths.ControllerConfigsDir));
        OpenStudioLogsCommand = new RelayCommand(() => _studio.OpenPath(StudioPaths.StudioLogsDir));
        ClearConsoleCommand = new RelayCommand(Logs.Clear);

        Maps.CollectionChanged += MapsChanged;
        _studio.LogReceived += line => Dispatcher.UIThread.Post(() => AppendLog(line));
        _studio.StatusChanged += (key, value) => Dispatcher.UIThread.Post(() => SetProcessStatus(key, value));

        RefreshConfigList();
        RefreshMaps();
        RefreshStatus();

        if (!StudioPaths.IsTrainingFromSourceAvailable())
            AppendLog("Test build: project src/ is not next to the app. Training and ONNX export (Python) are disabled. Launch Agent still works if controller + config + model are on disk.");
    }

    public string Title { get; }
    public ObservableCollection<string> Logs { get; } = [];
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

    public void SetMapsFolder(string folder)
    {
        MapsFolder = folder;
        RefreshMaps();
    }

    public void SaveWindowState(double x, double y, double width, double height, bool maximized)
    {
        _state.WindowX = (int)x;
        _state.WindowY = (int)y;
        _state.WindowWidth = (int)width;
        _state.WindowHeight = (int)height;
        _state.WindowMaximized = maximized;
        SaveState();
    }

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
            var vm = new MapItemViewModel(map);
            vm.PropertyChanged += (_, e) =>
            {
                if (e.PropertyName == nameof(MapItemViewModel.IsSelected))
                {
                    UpdateMapsStatus();
                    SaveState();
                }
            };
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
    }

    private void AppendLog(string line)
    {
        Logs.Add($"[{DateTime.Now:HH:mm:ss}] {line}");
        while (Logs.Count > MaxVisibleLogLines)
            Logs.RemoveAt(0);

        RefreshFileStatusOnly();
    }

    private void UpdateMapsStatus() =>
        MapsStatus = $"Maps scanned: {Maps.Count}. Selected: {Maps.Count(item => item.IsSelected)}.";

    private void MapsChanged(object? sender, NotifyCollectionChangedEventArgs e) => UpdateMapsStatus();

    private void SaveState()
    {
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
}
