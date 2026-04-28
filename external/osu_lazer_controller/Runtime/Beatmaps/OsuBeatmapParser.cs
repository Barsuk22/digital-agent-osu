using System.Globalization;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Beatmaps;

public sealed class OsuBeatmapParser
{
    private const int SchemaVersion = 1;

    public BridgeBeatmap Parse(string path)
    {
        var lines = File.ReadAllLines(path);
        var section = "";

        var metadata = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var difficulty = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        var timingPoints = new List<BridgeTimingPoint>();
        var hitObjects = new List<BridgeHitObject>();

        foreach (var raw in lines)
        {
            var line = raw.Trim();

            if (string.IsNullOrWhiteSpace(line) || line.StartsWith("//"))
                continue;

            if (line.StartsWith("[") && line.EndsWith("]"))
            {
                section = line;
                continue;
            }

            if (section == "[Metadata]")
            {
                var pair = SplitKeyValue(line);
                if (pair is not null)
                    metadata[pair.Value.Key] = pair.Value.Value;
            }
            else if (section == "[Difficulty]")
            {
                var pair = SplitKeyValue(line);
                if (pair is not null && TryDouble(pair.Value.Value, out var value))
                    difficulty[pair.Value.Key] = value;
            }
            else if (section == "[TimingPoints]")
            {
                var tp = ParseTimingPoint(line);
                if (tp is not null)
                    timingPoints.Add(tp);
            }
            else if (section == "[HitObjects]")
            {
                var obj = ParseHitObject(line, hitObjects.Count, timingPoints, difficulty);
                if (obj is not null)
                    hitObjects.Add(obj);
            }
        }

        timingPoints = timingPoints.OrderBy(t => t.TimeMs).ToList();
        hitObjects = hitObjects.OrderBy(o => o.TimeMs).ToList();

        return new BridgeBeatmap(
            SchemaVersion: SchemaVersion,
            BeatmapPath: path,
            Title: metadata.GetValueOrDefault("Title", Path.GetFileNameWithoutExtension(path)),
            Artist: metadata.GetValueOrDefault("Artist", "Unknown"),
            Version: metadata.GetValueOrDefault("Version", "Unknown"),
            Difficulty: new BridgeDifficulty(
                Hp: difficulty.GetValueOrDefault("HPDrainRate", 5.0),
                Cs: difficulty.GetValueOrDefault("CircleSize", 5.0),
                Od: difficulty.GetValueOrDefault("OverallDifficulty", 5.0),
                Ar: difficulty.GetValueOrDefault("ApproachRate", difficulty.GetValueOrDefault("OverallDifficulty", 5.0)),
                SliderMultiplier: difficulty.GetValueOrDefault("SliderMultiplier", 1.4),
                SliderTickRate: difficulty.GetValueOrDefault("SliderTickRate", 1.0)),
            TimingPoints: timingPoints,
            HitObjects: hitObjects);
    }

    private static BridgeHitObject? ParseHitObject(
        string line,
        int index,
        IReadOnlyList<BridgeTimingPoint> timingPoints,
        IReadOnlyDictionary<string, double> difficulty)
    {
        var parts = line.Split(',');
        if (parts.Length < 5)
            return null;

        var x = Int(parts[0]);
        var y = Int(parts[1]);
        var time = Double(parts[2]);
        var type = Int(parts[3]);
        var hitsound = Int(parts[4]);

        var comboIndex = 0;
        var comboNumber = 0;

        var isCircle = (type & 1) != 0;
        var isSlider = (type & 2) != 0;
        var isSpinner = (type & 8) != 0;

        if (isCircle)
        {
            return new BridgeHitObject(
                index, "circle", time, x, y, comboIndex, comboNumber, hitsound,
                null, null, null, null, null, null, null, null, null);
        }

        if (isSpinner && parts.Length >= 6)
        {
            var endTime = Double(parts[5]);

            return new BridgeHitObject(
                index, "spinner", time, x, y, comboIndex, comboNumber, hitsound,
                endTime, null, null, null, null, endTime - time, null, null, null);
        }

        if (isSlider && parts.Length >= 8)
        {
            var curveParts = parts[5].Split('|');
            var curveType = curveParts[0];

            var controlPoints = new List<BridgePoint>
            {
                new(x, y),
            };

            foreach (var pointRaw in curveParts.Skip(1))
            {
                var xy = pointRaw.Split(':');
                if (xy.Length != 2)
                    continue;

                controlPoints.Add(new BridgePoint(Double(xy[0]), Double(xy[1])));
            }

            var repeats = Math.Max(1, Int(parts[6]));
            var pixelLength = Double(parts[7]);

            var sliderMultiplier = difficulty.GetValueOrDefault("SliderMultiplier", 1.4);
            var duration = CalculateSliderDuration(time, pixelLength, repeats, sliderMultiplier, timingPoints);

            var sampled = SampleSliderPath(curveType, controlPoints, pixelLength);
            var cumulative = BuildCumulativeLengths(sampled);
            var totalLength = cumulative.Count > 0 ? cumulative[^1] : pixelLength;

            return new BridgeHitObject(
                index, "slider", time, x, y, comboIndex, comboNumber, hitsound,
                time + duration,
                curveType,
                controlPoints,
                repeats,
                pixelLength,
                duration,
                sampled,
                cumulative,
                totalLength);
        }

        return null;
    }

    private static double CalculateSliderDuration(
        double timeMs,
        double pixelLength,
        int repeats,
        double sliderMultiplier,
        IReadOnlyList<BridgeTimingPoint> timingPoints)
    {
        var beatLength = 500.0;
        var velocityMultiplier = 1.0;

        foreach (var tp in timingPoints.OrderBy(t => t.TimeMs))
        {
            if (tp.TimeMs > timeMs)
                break;

            if (tp.Uninherited)
                beatLength = tp.BeatLength;
            else if (tp.BeatLength < 0)
                velocityMultiplier = -100.0 / tp.BeatLength;
        }

        var scoringDistance = 100.0 * sliderMultiplier * velocityMultiplier;
        if (scoringDistance <= 0.001)
            scoringDistance = 100.0;

        return (pixelLength * repeats / scoringDistance) * beatLength;
    }

    private static List<BridgePoint> SampleSliderPath(string curveType, List<BridgePoint> points, double pixelLength)
    {
        if (points.Count <= 1)
            return points;

        var raw = curveType switch
        {
            "L" => SampleLinear(points),
            "B" => SampleBezier(points),
            "C" => SampleCatmull(points),
            "P" => SampleBezier(points),
            _ => SampleBezier(points),
        };

        return TrimOrExtend(raw, pixelLength);
    }

    private static List<BridgePoint> SampleLinear(List<BridgePoint> points)
    {
        var result = new List<BridgePoint>();

        for (var i = 0; i < points.Count - 1; i++)
        {
            var a = points[i];
            var b = points[i + 1];
            var dist = Distance(a, b);
            var steps = Math.Max(2, (int)Math.Ceiling(dist / 4.0));

            for (var s = 0; s < steps; s++)
            {
                var t = s / (double)steps;
                result.Add(Lerp(a, b, t));
            }
        }

        result.Add(points[^1]);
        return result;
    }

    private static List<BridgePoint> SampleBezier(List<BridgePoint> points)
    {
        var result = new List<BridgePoint>();
        var steps = Math.Max(24, points.Count * 24);

        for (var i = 0; i <= steps; i++)
        {
            var t = i / (double)steps;
            result.Add(DeCasteljau(points, t));
        }

        return result;
    }

    private static List<BridgePoint> SampleCatmull(List<BridgePoint> points)
    {
        if (points.Count < 2)
            return points;

        var result = new List<BridgePoint>();

        for (var i = 0; i < points.Count - 1; i++)
        {
            var p0 = points[Math.Max(i - 1, 0)];
            var p1 = points[i];
            var p2 = points[i + 1];
            var p3 = points[Math.Min(i + 2, points.Count - 1)];

            for (var s = 0; s < 16; s++)
            {
                var t = s / 16.0;
                result.Add(CatmullRom(p0, p1, p2, p3, t));
            }
        }

        result.Add(points[^1]);
        return result;
    }

    private static List<BridgePoint> TrimOrExtend(List<BridgePoint> points, double targetLength)
    {
        if (points.Count <= 1 || targetLength <= 0)
            return points;

        var result = new List<BridgePoint> { points[0] };
        var travelled = 0.0;

        for (var i = 1; i < points.Count; i++)
        {
            var prev = points[i - 1];
            var current = points[i];
            var segment = Distance(prev, current);

            if (travelled + segment >= targetLength)
            {
                var remain = targetLength - travelled;
                var t = segment <= 0.0001 ? 0.0 : remain / segment;
                result.Add(Lerp(prev, current, t));
                return result;
            }

            travelled += segment;
            result.Add(current);
        }

        return result;
    }

    private static List<double> BuildCumulativeLengths(List<BridgePoint> points)
    {
        var result = new List<double>();
        var total = 0.0;

        if (points.Count == 0)
            return result;

        result.Add(0.0);

        for (var i = 1; i < points.Count; i++)
        {
            total += Distance(points[i - 1], points[i]);
            result.Add(total);
        }

        return result;
    }

    private static BridgeTimingPoint? ParseTimingPoint(string line)
    {
        var parts = line.Split(',');
        if (parts.Length < 2)
            return null;

        return new BridgeTimingPoint(
            TimeMs: Double(parts[0]),
            BeatLength: Double(parts[1]),
            Meter: parts.Length > 2 ? Int(parts[2]) : 4,
            SampleSet: parts.Length > 3 ? Int(parts[3]) : 1,
            SampleIndex: parts.Length > 4 ? Int(parts[4]) : 0,
            Volume: parts.Length > 5 ? Int(parts[5]) : 100,
            Uninherited: parts.Length <= 6 || Int(parts[6]) == 1,
            Effects: parts.Length > 7 ? Int(parts[7]) : 0);
    }

    private static (string Key, string Value)? SplitKeyValue(string line)
    {
        var index = line.IndexOf(':');
        if (index <= 0)
            return null;

        return (line[..index].Trim(), line[(index + 1)..].Trim());
    }

    private static BridgePoint DeCasteljau(IReadOnlyList<BridgePoint> points, double t)
    {
        var temp = points.ToList();

        for (var level = 1; level < points.Count; level++)
        {
            for (var i = 0; i < points.Count - level; i++)
            {
                temp[i] = Lerp(temp[i], temp[i + 1], t);
            }
        }

        return temp[0];
    }

    private static BridgePoint CatmullRom(BridgePoint p0, BridgePoint p1, BridgePoint p2, BridgePoint p3, double t)
    {
        var t2 = t * t;
        var t3 = t2 * t;

        return new BridgePoint(
            0.5 * ((2 * p1.X) + (-p0.X + p2.X) * t + (2 * p0.X - 5 * p1.X + 4 * p2.X - p3.X) * t2 + (-p0.X + 3 * p1.X - 3 * p2.X + p3.X) * t3),
            0.5 * ((2 * p1.Y) + (-p0.Y + p2.Y) * t + (2 * p0.Y - 5 * p1.Y + 4 * p2.Y - p3.Y) * t2 + (-p0.Y + 3 * p1.Y - 3 * p2.Y + p3.Y) * t3));
    }

    private static BridgePoint Lerp(BridgePoint a, BridgePoint b, double t)
        => new(a.X + (b.X - a.X) * t, a.Y + (b.Y - a.Y) * t);

    private static double Distance(BridgePoint a, BridgePoint b)
        => Math.Sqrt(Math.Pow(b.X - a.X, 2) + Math.Pow(b.Y - a.Y, 2));

    private static bool TryDouble(string value, out double result)
        => double.TryParse(value.Replace(',', '.'), NumberStyles.Float, CultureInfo.InvariantCulture, out result);

    private static double Double(string value)
        => TryDouble(value, out var result) ? result : 0.0;

    private static int Int(string value)
        => int.TryParse(value, NumberStyles.Integer, CultureInfo.InvariantCulture, out var result) ? result : 0;
}