import os
from datetime import datetime

# === ROOT проекта ===
PROJECT_ROOT = r"D:\Projects\digital_agent_osu_project"

# === куда сохраняем ===
EXPORT_DIR = os.path.join(PROJECT_ROOT, "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# === список файлов ===
FILES = [
    "src/apps/serve_osu_policy.py",
    "src/apps/export_osu_lazer_bridge_map.py",
    "src/apps/compare_osu_lazer_bridge_obs.py",
    "src/skills/osu/env/osu_env.py",
    "src/skills/osu/domain/slider_path.py",
    "src/skills/osu/reward/judgement.py",
    "src/skills/osu/parser/osu_parser.py",
    "external/osu_lazer_controller/OsuLazerController/Observation/ObservationBuilder.cs",
    "external/osu_lazer_controller/OsuLazerController/Loop/RuntimeLoop.cs",
    "external/osu_lazer_controller/OsuLazerController/Domain/BeatmapSession.cs",
    "external/osu_lazer_controller/OsuLazerController/Domain/BeatmapModels.cs",
    "external/osu_lazer_controller/OsuLazerController/Mapping/PlayfieldMapper.cs",
    "external/osu_lazer_controller/OsuLazerController/IPC/PolicyClient.cs",
    "external/osu_lazer_controller/OsuLazerController/App/ControllerApp.cs",
    "external/osu_lazer_controller/OsuLazerController/App/RuntimeConfig.cs",
]

# === имя файла ===
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_path = os.path.join(EXPORT_DIR, f"osu_lazer_bridge_export_{timestamp}.txt")


def read_file_safe(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="cp1251", errors="ignore") as f:
            return f.read()
    except Exception as e:
        return f"[ERROR READING FILE: {e}]"


with open(output_path, "w", encoding="utf-8") as out:
    out.write("=== OSU LAZER BRIDGE EXPORT ===\n")
    out.write(f"Generated at: {timestamp}\n\n")

    for rel_path in FILES:
        abs_path = os.path.join(PROJECT_ROOT, rel_path)

        out.write("=" * 80 + "\n")
        out.write(f"FILE: {rel_path}\n")
        out.write("=" * 80 + "\n\n")

        if not os.path.exists(abs_path):
            out.write("[FILE NOT FOUND]\n\n")
            continue

        content = read_file_safe(abs_path)
        out.write(content)
        out.write("\n\n\n")

print(f"[DONE] Export saved to: {output_path}")