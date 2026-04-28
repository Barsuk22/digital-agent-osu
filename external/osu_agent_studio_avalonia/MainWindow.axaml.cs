using System.Collections.Specialized;
using Avalonia.Controls;
using Avalonia.Interactivity;
using Avalonia.Platform.Storage;
using OsuAgentStudio.Avalonia.ViewModels;

namespace OsuAgentStudio.Avalonia;

public sealed partial class MainWindow : Window
{
    private readonly MainWindowViewModel _viewModel;

    public MainWindow()
    {
        InitializeComponent();
        _viewModel = new MainWindowViewModel();
        DataContext = _viewModel;

        var state = _viewModel.GetState();
        Width = state.WindowWidth;
        Height = state.WindowHeight;
        if (state.WindowX > 0 || state.WindowY > 0)
            Position = new global::Avalonia.PixelPoint(state.WindowX, state.WindowY);
        if (state.WindowMaximized)
            WindowState = WindowState.Maximized;

        _viewModel.Logs.CollectionChanged += Logs_CollectionChanged;
        Closing += (_, _) =>
        {
            var maximized = WindowState == WindowState.Maximized;
            _viewModel.SaveWindowState(Position.X, Position.Y, Width, Height, maximized);
            _viewModel.Shutdown();
        };
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
        if (_viewModel.Logs.Count == 0)
            return;

        ConsoleList.ScrollIntoView(_viewModel.Logs[^1]);
    }
}
