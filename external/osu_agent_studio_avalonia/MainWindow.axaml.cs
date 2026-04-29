using System.Collections.Specialized;
using Avalonia;
using Avalonia.Input;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using Avalonia.Threading;
using Avalonia.VisualTree;

using OsuAgentStudio.Avalonia.ViewModels;

namespace OsuAgentStudio.Avalonia;

public sealed partial class MainWindow : Window
{
    private readonly MainWindowViewModel _viewModel;
    private ScrollViewer? _consoleScrollViewer;
    private bool _autoScrollConsole = true;
    private bool _keepFullscreen = true;

    public MainWindow() 
    {
        InitializeComponent();
        var iconPath = Path.Combine(AppContext.BaseDirectory, "app.ico");
        if (File.Exists(iconPath))
            Icon = new WindowIcon(iconPath);

        _viewModel = new MainWindowViewModel();
        DataContext = _viewModel;

        Opened += async (_, _) =>
        {
            EnforceFullscreen();
            await AnimateWelcomeIn();
        };
        Activated += (_, _) => EnforceFullscreen();
        PropertyChanged += MainWindow_PropertyChanged;

        var state = _viewModel.GetState();
        Width = state.WindowWidth;
        Height = state.WindowHeight;
        if (state.WindowX > 0 || state.WindowY > 0)
            Position = new global::Avalonia.PixelPoint(state.WindowX, state.WindowY);
        WindowState = WindowState.FullScreen;

        _viewModel.Logs.CollectionChanged += Logs_CollectionChanged;
        ConsoleList.AttachedToVisualTree += (_, _) =>
            Dispatcher.UIThread.Post(AttachConsoleScrollViewer, DispatcherPriority.Loaded);
        ConsoleList.PointerWheelChanged += ConsoleList_PointerWheelChanged;
        Closing += (_, _) =>
        {
            var maximized = WindowState is WindowState.Maximized or WindowState.FullScreen;
            _viewModel.SaveNow();
            _viewModel.SaveWindowState(Position.X, Position.Y, Width, Height, maximized);
            _viewModel.Shutdown();
        };
    }

    private async Task AnimateWelcomeIn()
    {
        if (!_viewModel.IsWelcomeVisible)
            return;

        WelcomeOverlay.Opacity = 1;

        WelcomeBackground.Opacity = 0;
        WelcomeDim.Opacity = 0;
        WelcomeCard.Opacity = 0;
        WelcomeTitleText.Opacity = 0;
        WelcomeBodyText.Opacity = 0;
        WelcomeStartButton.Opacity = 0;

        await FadeTo(WelcomeBackground, 1.0, 650);

        var dimTask = FadeTo(WelcomeDim, 1.0, 900);

        await Task.Delay(180);
        await FadeTo(WelcomeCard, 1.0, 420);
        await FadeTo(WelcomeTitleText, 1.0, 260);
        await FadeTo(WelcomeBodyText, 1.0, 260);
        await FadeTo(WelcomeStartButton, 1.0, 260);

        await dimTask;
    }

    private async void StartWork_Click(object? sender, RoutedEventArgs e)
    {
        await FadeTo(WelcomeOverlay, 0.0, 420);
        _viewModel.IsWelcomeVisible = false;
    }

    private static async Task FadeTo(Control control, double targetOpacity, int milliseconds)
    {
        var startOpacity = control.Opacity;
        const int steps = 30;

        for (var i = 1; i <= steps; i++)
        {
            var t = i / (double)steps;
            control.Opacity = startOpacity + (targetOpacity - startOpacity) * t;
            await Task.Delay(milliseconds / steps);
        }

        control.Opacity = targetOpacity;
    }

    private async void BrowseMapsFolder_Click(object? sender, RoutedEventArgs e)
    {
        var folders = await StorageProvider.OpenFolderPickerAsync(new FolderPickerOpenOptions
        {
            Title = "Choose folder with .osu beatmaps",
            AllowMultiple = false,
        });

        var folder = folders.FirstOrDefault();
        if (folder?.Path.LocalPath is { Length: > 0 } path)
            _viewModel.SetMapsFolder(path);
    }

    private void Logs_CollectionChanged(object? sender, NotifyCollectionChangedEventArgs e)
    {
        AttachConsoleScrollViewer();
        if (!_autoScrollConsole || _viewModel.Logs.Count == 0)
            return;

        Dispatcher.UIThread.Post(() =>
        {
            if (_autoScrollConsole && _viewModel.Logs.Count > 0)
                ScrollConsoleToBottom();
        }, DispatcherPriority.Background);
    }

    private void TitleBar_PointerPressed(object? sender, PointerPressedEventArgs e)
    {
        if (e.GetCurrentPoint(this).Properties.IsLeftButtonPressed)
            BeginMoveDrag(e);
    }

    private void Minimize_Click(object? sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;

    private void Maximize_Click(object? sender, RoutedEventArgs e)
    {
        _keepFullscreen = WindowState != WindowState.FullScreen;
        WindowState = _keepFullscreen ? WindowState.FullScreen : WindowState.Maximized;
    }

    private void Close_Click(object? sender, RoutedEventArgs e) => Close();

    private void MainWindow_PropertyChanged(object? sender, AvaloniaPropertyChangedEventArgs e)
    {
        if (e.Property != WindowStateProperty)
            return;

        if (!_keepFullscreen || WindowState is WindowState.FullScreen or WindowState.Minimized)
            return;

        Dispatcher.UIThread.Post(EnforceFullscreen, DispatcherPriority.Background);
    }

    private void EnforceFullscreen()
    {
        if (_keepFullscreen && WindowState != WindowState.Minimized && WindowState != WindowState.FullScreen)
            WindowState = WindowState.FullScreen;
    }

    private void ConsoleScrollViewer_ScrollChanged(object? sender, ScrollChangedEventArgs e)
    {
        UpdateConsoleAutoScrollState();
    }

    private void ConsoleList_PointerWheelChanged(object? sender, PointerWheelEventArgs e)
    {
        if (e.Delta.Y > 0)
        {
            _autoScrollConsole = false;
            return;
        }

        Dispatcher.UIThread.Post(UpdateConsoleAutoScrollState, DispatcherPriority.Background);
    }

    private void AttachConsoleScrollViewer()
    {
        if (_consoleScrollViewer is not null)
            return;

        _consoleScrollViewer = FindDescendant<ScrollViewer>(ConsoleList);
        if (_consoleScrollViewer is null)
            return;

        _consoleScrollViewer.ScrollChanged += ConsoleScrollViewer_ScrollChanged;
        UpdateConsoleAutoScrollState();
    }

    private void UpdateConsoleAutoScrollState()
    {
        if (_consoleScrollViewer is null)
            return;

        var distanceFromBottom = _consoleScrollViewer.Extent.Height
            - _consoleScrollViewer.Offset.Y
            - _consoleScrollViewer.Viewport.Height;

        _autoScrollConsole = distanceFromBottom <= 24;
    }

    private void ScrollConsoleToBottom()
    {
        if (_consoleScrollViewer is null)
        {
            ConsoleList.ScrollIntoView(_viewModel.Logs[^1]);
            return;
        }

        _consoleScrollViewer.Offset = new Vector(
            _consoleScrollViewer.Offset.X,
            Math.Max(0, _consoleScrollViewer.Extent.Height));
    }

    private static T? FindDescendant<T>(Control root)
        where T : Control
    {
        foreach (var child in root.GetVisualChildren())
        {
            if (child is T match)
                return match;

            if (child is Control childControl)
            {
                var nested = FindDescendant<T>(childControl);
                if (nested is not null)
                    return nested;
            }
        }

        return null;
    }
}
