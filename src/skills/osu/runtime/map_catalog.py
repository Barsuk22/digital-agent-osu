from __future__ import annotations

from pathlib import Path

from src.core.config.paths import PATHS


MAP_ALIASES: dict[str, Path] = {
    "spica_beginner": PATHS.beginner_ka_map,
    "spica_easy": PATHS.easy_ka_map,
    "sentimental_love_easy": PATHS.sentiment_easy_map,
    "chikatto_easy": PATHS.chikatto_easy_map,
    "dame_beginner": PATHS.suzuki_dame_beginner_map,
    "itowanai_easy": PATHS.miminari_itowanai_easy_map,
    "megane_easy": PATHS.noa_megane_easy_map,
    "kouga_easy": PATHS.onmyo_kouga_easy_map,
    "internet_yamero_easy": PATHS.internet_yamero_easy_map,
    "yasashii_suisei_easy": PATHS.yasashii_suisei_easy_map,
}


def resolve_map_alias(value: str) -> Path:
    candidate = MAP_ALIASES.get(value)
    if candidate is not None:
        return candidate

    path = Path(value)
    if path.exists():
        return path

    raise KeyError(
        f"Unknown map alias '{value}'. Available aliases: {', '.join(sorted(MAP_ALIASES))}"
    )
