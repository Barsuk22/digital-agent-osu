using OsuAgentStudio.Core;

namespace OsuAgentStudio.Avalonia.ViewModels;

public sealed class MapItemViewModel : ObservableObject
{
    private readonly Action? _selectionChanged;
    private bool _isSelected;

    public MapItemViewModel(MapItem item, Action? selectionChanged = null)
    {
        _selectionChanged = selectionChanged;
        Path = item.Path;
        DisplayName = item.DisplayName;
        _isSelected = item.IsSelected;
    }

    public string Path { get; }
    public string DisplayName { get; }

    public bool IsSelected
    {
        get => _isSelected;
        set
        {
            if (SetProperty(ref _isSelected, value))
                _selectionChanged?.Invoke();
        }
    }
}
