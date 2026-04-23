using Microsoft.ML.OnnxRuntime;
using Microsoft.ML.OnnxRuntime.Tensors;
using OsuLazerController.Config;
using OsuLazerController.Models;

namespace OsuLazerController.Runtime.Bridge;

public sealed class OnnxPolicyBridge : IPolicyBridge, IDisposable
{
    private readonly InferenceSession _session;
    private readonly string _inputName;
    private readonly string _outputName;

    public OnnxPolicyBridge(PolicyBridgeConfig config)
    {
        if (string.IsNullOrWhiteSpace(config.ModelPath))
        {
            throw new ArgumentException("PolicyBridge.ModelPath must be set for onnx mode.");
        }

        var modelPath = Path.GetFullPath(config.ModelPath);
        if (!File.Exists(modelPath))
        {
            throw new FileNotFoundException("ONNX model not found.", modelPath);
        }

        var options = new SessionOptions();
        options.GraphOptimizationLevel = GraphOptimizationLevel.ORT_ENABLE_ALL;
        _session = new InferenceSession(modelPath, options);

        _inputName = _session.InputMetadata.Keys.FirstOrDefault()
            ?? throw new InvalidOperationException("ONNX model does not expose any inputs.");
        _outputName = _session.OutputMetadata.Keys.FirstOrDefault()
            ?? throw new InvalidOperationException("ONNX model does not expose any outputs.");
    }

    public Task<ActionPacket> RequestActionAsync(ObservationPacket observation, CancellationToken cancellationToken = default)
    {
        cancellationToken.ThrowIfCancellationRequested();

        var tensor = new DenseTensor<float>(new[] { 1, observation.Obs.Length });
        for (var index = 0; index < observation.Obs.Length; index++)
        {
            tensor[0, index] = observation.Obs[index];
        }

        var inputs = new List<NamedOnnxValue>
        {
            NamedOnnxValue.CreateFromTensor(_inputName, tensor),
        };
        using var outputs = _session.Run(inputs);
        var outputTensor = outputs.First(value => value.Name == _outputName).AsTensor<float>();
        var values = outputTensor.ToArray();
        if (values.Length < 3)
        {
            throw new InvalidOperationException($"Expected at least 3 output values from ONNX model, got {values.Length}.");
        }

        return Task.FromResult(
            new ActionPacket(
                Dx: values[0],
                Dy: values[1],
                ClickStrength: values[2]));
    }

    public void Dispose()
    {
        _session.Dispose();
    }
}
