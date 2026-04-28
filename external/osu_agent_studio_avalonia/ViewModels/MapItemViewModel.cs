using OsuAgentStudio.Core;

namespace OsuAgentStudio.Avalonia.ViewModels;

public sealed class MapItemViewModel : ObservableObject
{
    private bool _isSelected;

    public MapItemViewModel(MapItem item)
    {
        Path = item.Path;
        DisplayName = item.DisplayName;
        _isSelected = item.IsSelected;
    }

    public string Path { get; }
    public string DisplayName { get; }

    public bool IsSelected
    {
        get => _isSelected;
        set => SetProperty(ref _isSelected, value);
    }
}
