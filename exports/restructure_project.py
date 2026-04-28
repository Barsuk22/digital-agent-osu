from pathlib import Path
import shutil


ROOT = Path(r"D:/Projects/digital_agent_osu_project")


def log(msg: str) -> None:
    print(msg)


def ensure_dir(path: Path, make_package: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if make_package:
        init_file = path / "__init__.py"
        if not init_file.exists():
            init_file.touch()
            log(f"[create file] {init_file}")


def ensure_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")
        log(f"[create file] {path}")


def move_path(src: Path, dest: Path) -> None:
    if not src.exists():
        return

    if dest.exists():
        log(f"[skip move exists] {dest}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    log(f"[move] {src} -> {dest}")


def merge_dir_contents(src_dir: Path, dest_dir: Path) -> None:
    """
    Переносит содержимое src_dir в dest_dir поэлементно.
    Если элемент уже есть в dest_dir, не трогает его.
    """
    if not src_dir.exists() or not src_dir.is_dir():
        return

    ensure_dir(dest_dir)

    for item in src_dir.iterdir():
        target = dest_dir / item.name
        if target.exists():
            log(f"[skip merge exists] {target}")
            continue
        shutil.move(str(item), str(target))
        log(f"[merge move] {item} -> {target}")


def remove_dir_if_empty(path: Path) -> None:
    if path.exists() and path.is_dir():
        try:
            next(path.iterdir())
        except StopIteration:
            path.rmdir()
            log(f"[remove empty dir] {path}")


def remove_word_lock_files(path: Path) -> None:
    if not path.exists():
        return

    for file in path.rglob("~$*.docx"):
        try:
            file.unlink()
            log(f"[remove lock file] {file}")
        except Exception as exc:
            log(f"[warn] could not remove {file}: {exc}")


def write_if_empty(path: Path, content: str) -> None:
    if not path.exists():
        ensure_file(path, content)
        return

    try:
        existing = path.read_text(encoding="utf-8").strip()
    except Exception:
        existing = ""

    if not existing:
        path.write_text(content, encoding="utf-8")
        log(f"[fill file] {path}")


def main() -> None:
    root = ROOT

    # ------------------------------------------------------------------
    # 1. Базовые важные папки artifacts
    # ------------------------------------------------------------------
    top_artifacts = root / "artifacts"
    ensure_dir(top_artifacts)
    for sub in ["checkpoints", "logs", "metrics", "debug", "exports", "runs"]:
        ensure_dir(top_artifacts / sub)

    # ------------------------------------------------------------------
    # 2. Перенос data/artifacts -> artifacts
    # ------------------------------------------------------------------
    data_artifacts = root / "data" / "artifacts"

    for name in ["checkpoints", "debug", "exports", "logs", "metrics"]:
        src = data_artifacts / name
        dest = top_artifacts / name

        if src.exists():
            # Если верхняя папка уже есть, аккуратно вливаем содержимое
            if dest.exists():
                merge_dir_contents(src, dest)
                remove_dir_if_empty(src)
            else:
                move_path(src, dest)

    # Если data/artifacts опустела — удалить
    remove_dir_if_empty(data_artifacts)

    # ------------------------------------------------------------------
    # 3. Добиваем структуру runs/osu_phase1_ppo
    # ------------------------------------------------------------------
    phase_dir = top_artifacts / "runs" / "osu_phase1_ppo"
    for sub in ["checkpoints", "logs", "metrics", "eval", "replays"]:
        ensure_dir(phase_dir / sub)

    # ------------------------------------------------------------------
    # 4. Недостающие yaml для osu
    # ------------------------------------------------------------------
    configs_osu = root / "configs" / "osu"

    maps_yaml = configs_osu / "maps.yaml"
    judgement_yaml = configs_osu / "judgement.yaml"

    write_if_empty(
        maps_yaml,
        """# osu maps registry
# train/eval splits, pools, active maps by phase

maps: []

train_pools:
  phase0: []
  phase1: []
  phase2: []
  phase3: []

eval_pools:
  default: []
""",
    )

    write_if_empty(
        judgement_yaml,
        """# osu judgement configuration
# timing windows, hit radius logic, slider/spinner thresholds

timing:
  use_od: true

hit_windows:
  great_ms: null
  good_ms: null
  meh_ms: null

radius:
  use_circle_size: true
  scale: 1.0

slider:
  head_only_phase4: true
  require_follow: false
  tick_reward_enabled: false

spinner:
  enabled: true
  min_spin_rate: 0.0
""",
    )

    # ------------------------------------------------------------------
    # 5. Док по stability gate / skill extraction gate
    # ------------------------------------------------------------------
    skill_gate_doc = root / "docs" / "osu" / "skill_extraction_gate.md"
    write_if_empty(
        skill_gate_doc,
        """# Skill Extraction Gate

## Цель
Проверить, что агент уже играет не случайно, а повторяемо, и только потом включать извлечение навыков.

## Что проверяем
- hit rate стабилен
- useful clicks стабилизировались
- timing drift не хаотичный
- успешные паттерны повторяются
- хорошие эпизоды похожи друг на друга

## Критерий прохождения
- агент показывает повторяемое поведение
- успешные куски можно кластеризовать
- извлечённые паттерны выглядят как реальные заготовки навыков, а не случайное везение

## Следующий шаг
После прохождения gate можно переходить к Skill Memory Init.
""",
    )

    # ------------------------------------------------------------------
    # 6. Apps entrypoints
    # ------------------------------------------------------------------
    apps = root / "src" / "apps"
    ensure_dir(apps, make_package=True)

    app_files = {
        "train_osu.py": "",
        "eval_osu.py": "",
        "replay_osu.py": "",
        "live_viewer_osu.py": "",
        "parse_osu_map.py": "",
    }
    for fname, content in app_files.items():
        ensure_file(apps / fname, content)

    # ------------------------------------------------------------------
    # 7. Убедиться, что evaluation — пакет
    # ------------------------------------------------------------------
    ensure_dir(root / "src" / "skills" / "osu" / "evaluation", make_package=True)

    # ------------------------------------------------------------------
    # 8. Пакетность для основных src-папок
    # ------------------------------------------------------------------
    package_dirs = [
        root / "src",
        root / "src" / "core",
        root / "src" / "girl",
        root / "src" / "agent",
        root / "src" / "learning",
        root / "src" / "memory",
        root / "src" / "skills",
        root / "src" / "skills" / "osu",
        root / "src" / "storage",
        root / "src" / "world",
        root / "src" / "learning" / "rl",
        root / "src" / "learning" / "rl" / "ppo",
        root / "src" / "learning" / "rl" / "buffers",
        root / "src" / "learning" / "rl" / "samplers",
        root / "src" / "learning" / "rl" / "trainers",
        root / "src" / "skills" / "osu" / "curriculum",
        root / "src" / "skills" / "osu" / "domain",
        root / "src" / "skills" / "osu" / "env",
        root / "src" / "skills" / "osu" / "parser",
        root / "src" / "skills" / "osu" / "reward",
        root / "src" / "skills" / "osu" / "replay",
        root / "src" / "skills" / "osu" / "training",
        root / "src" / "skills" / "osu" / "viewer",
    ]
    for pkg_dir in package_dirs:
        ensure_dir(pkg_dir, make_package=True)

    # ------------------------------------------------------------------
    # 9. Новая структура unit tests под osu
    # ------------------------------------------------------------------
    tests_unit_osu = root / "tests" / "unit" / "osu"
    for sub in ["parser", "env", "reward", "domain", "viewer", "curriculum"]:
        ensure_dir(tests_unit_osu / sub)
        ensure_file(tests_unit_osu / sub / ".gitkeep")

    # Перенос старых unit test папок
    old_to_new = {
        root / "tests" / "unit" / "parser": root / "tests" / "unit" / "osu" / "parser",
        root / "tests" / "unit" / "env": root / "tests" / "unit" / "osu" / "env",
        root / "tests" / "unit" / "reward": root / "tests" / "unit" / "osu" / "reward",
    }

    for old_dir, new_dir in old_to_new.items():
        if old_dir.exists():
            merge_dir_contents(old_dir, new_dir)
            remove_dir_if_empty(old_dir)

    # Сохраняем memory и skills как есть, но гарантируем .gitkeep
    ensure_dir(root / "tests" / "unit" / "memory")
    ensure_dir(root / "tests" / "unit" / "skills")
    ensure_file(root / "tests" / "unit" / "memory" / ".gitkeep")
    ensure_file(root / "tests" / "unit" / "skills" / ".gitkeep")

    # ------------------------------------------------------------------
    # 10. module_map подсказка про girl vs agent
    # ------------------------------------------------------------------
    module_map = root / "docs" / "architecture" / "module_map.md"
    append_block = """

## girl vs agent

### `src/girl`
Отвечает за character brain:
- persona
- thought
- state
- style
- initiative
- memory bridge
- orchestration

### `src/agent`
Отвечает за execution layer:
- planner
- decision
- controller
- runtime

Коротко:
- girl = кто она
- agent = как она действует
"""
    if module_map.exists():
        try:
            text = module_map.read_text(encoding="utf-8")
        except Exception:
            text = ""
        if "## girl vs agent" not in text:
            module_map.write_text(text.rstrip() + "\n" + append_block, encoding="utf-8")
            log(f"[append doc] {module_map}")
    else:
        ensure_file(module_map, append_block.lstrip())

    # ------------------------------------------------------------------
    # 11. Чистим мусорные Word lock-файлы
    # ------------------------------------------------------------------
    remove_word_lock_files(root / "projectDocs")

    # ------------------------------------------------------------------
    # 12. Ещё раз пробуем удалить пустой data/artifacts
    # ------------------------------------------------------------------
    remove_dir_if_empty(root / "data" / "artifacts")

    log("\n[done] Project restructure completed.")


if __name__ == "__main__":
    main()