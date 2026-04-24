using OsuLazerController.Config;
using OsuLazerController.Runtime;
using OsuLazerController.Runtime.Win32;

DpiAwareness.Enable();
var configPath = args.Length > 0 ? args[0] : null;
var config = RuntimeConfig.Load(configPath);
var app = new ControllerApplication(config);
return await app.RunAsync();
