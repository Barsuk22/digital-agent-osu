using Avalonia.Media;

namespace OsuAgentStudio.Avalonia.ViewModels;

public sealed record LogLineViewModel(
    string Text,
    IBrush Brush,
    string Kind,
    string Prefix,
    string RewardText,
    string BetweenRewardAndMiss,
    string MissText,
    string Suffix);
