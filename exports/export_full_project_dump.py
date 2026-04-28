from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path


# Какие папки вообще не трогаем
EXCLUDED_DIR_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "site-packages",
    "data",
    "artifacts",
    "docs",
    "exports",
    "projectDocs",
    ".dotnet_home",
}

# Какие отдельные файлы не надо брать
EXCLUDED_FILE_NAMES = {
    ".DS_Store",
    "Thumbs.db",
}

# Какие расширения считаем текстовыми и полезными для экспорта кода/конфигов
ALLOWED_EXTENSIONS = {
    ".py",
    ".pyi",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
    ".xml",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".csv",
    ".cs",
}

# Какие файлы без нормального suffix тоже можно включать
ALLOWED_BASENAMES = {
    "README",
    "README.md",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".env.example",
    "Dockerfile",
    "Makefile",
}


def is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts if part not in {".", ".."})


def should_skip_dir(dir_name: str) -> bool:
    return dir_name in EXCLUDED_DIR_NAMES


def should_include_file(path: Path) -> bool:
    name = path.name

    if name in EXCLUDED_FILE_NAMES:
        return False

    if name.endswith((".pyc", ".pyo", ".pyd")):
        return False

    if name in ALLOWED_BASENAMES:
        return True

    if path.suffix.lower() in ALLOWED_EXTENSIONS:
        return True

    return False


def is_probably_text_file(path: Path, sample_size: int = 4096) -> bool:
    try:
        with path.open("rb") as f:
            chunk = f.read(sample_size)
        if b"\x00" in chunk:
            return False
        return True
    except Exception:
        return False


def build_project_tree(root: Path, included_files: list[Path]) -> str:
    included_set = {p.resolve() for p in included_files}
    lines: list[str] = [root.name + "/"]

    def walk(directory: Path, prefix: str = "") -> None:
        entries = []
        try:
            for entry in directory.iterdir():
                if entry.is_dir():
                    if should_skip_dir(entry.name):
                        continue
                    entries.append(entry)
                else:
                    if entry.resolve() in included_set:
                        entries.append(entry)
        except PermissionError:
            return

        entries.sort(key=lambda p: (p.is_file(), p.name.lower()))

        for index, entry in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + entry.name + ("/" if entry.is_dir() else ""))

            if entry.is_dir():
                extension = "    " if is_last else "│   "
                walk(entry, prefix + extension)

    walk(root)
    return "\n".join(lines)


def collect_files(root: Path) -> list[Path]:
    collected: list[Path] = []

    for current_root, dirs, files in os.walk(root):
        current_path = Path(current_root)

        dirs[:] = [
            d for d in dirs
            if not should_skip_dir(d)
        ]
        dirs.sort()

        for file_name in sorted(files):
            file_path = current_path / file_name

            if not should_include_file(file_path):
                continue

            if not is_probably_text_file(file_path):
                continue

            collected.append(file_path)

    collected.sort(key=lambda p: str(p.relative_to(root)).lower())
    return collected


def safe_read_text(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "cp1251", "latin-1"]

    for encoding in encodings:
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            pass

    return "[[ERROR: could not decode file]]"


def export_project(root: Path, output_file: Path) -> None:
    files = collect_files(root)
    tree = build_project_tree(root, files)
    exported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as out:
        out.write("=" * 100 + "\n")
        out.write("PROJECT FULL EXPORT\n")
        out.write("=" * 100 + "\n\n")

        out.write(f"Root: {root}\n")
        out.write(f"Exported at: {exported_at}\n")
        out.write(f"Total exported files: {len(files)}\n\n")

        out.write("=" * 100 + "\n")
        out.write("PROJECT TREE\n")
        out.write("=" * 100 + "\n\n")
        out.write(tree)
        out.write("\n\n")

        out.write("=" * 100 + "\n")
        out.write("EXPORTED FILE LIST\n")
        out.write("=" * 100 + "\n\n")
        for file_path in files:
            relative_path = file_path.relative_to(root).as_posix()
            out.write(f"- {relative_path}\n")
        out.write("\n")

        for index, file_path in enumerate(files, start=1):
            relative_path = file_path.relative_to(root).as_posix()
            content = safe_read_text(file_path)

            out.write("\n" + "=" * 100 + "\n")
            out.write(f"FILE {index:04d}: {relative_path}\n")
            out.write("=" * 100 + "\n")
            out.write(f"Absolute path: {file_path}\n")
            out.write(f"Size: {file_path.stat().st_size} bytes\n")
            out.write("-" * 100 + "\n")
            out.write(content.rstrip())
            out.write("\n")

    print(f"[OK] Export completed: {output_file}")
    print(f"[OK] Files exported: {len(files)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export project source/config files into one formatted TXT file."
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=r"D:\Projects\digital_agent_osu_project",
        help="Root path of the project",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output TXT file path",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if not root.exists():
        raise FileNotFoundError(f"Project root does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Project root is not a directory: {root}")

    if args.output:
        output_file = Path(args.output).resolve()
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = root / "exports" / f"project_full_export_{timestamp}.txt"

    export_project(root=root, output_file=output_file)


if __name__ == "__main__":
    main()