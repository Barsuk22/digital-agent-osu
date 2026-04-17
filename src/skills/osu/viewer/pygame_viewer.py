from __future__ import annotations

import math
import sys
import time

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional

import pygame
import pygame.gfxdraw

from src.skills.osu.domain.math_utils import (
    OSU_PLAYFIELD_HEIGHT,
    OSU_PLAYFIELD_WIDTH,
    distance,
    osu_circle_radius,
)
from src.skills.osu.domain.models import HitObjectType, SliderObject
from src.skills.osu.domain.osu_rules import ar_to_preempt_ms, slider_duration_ms
from src.skills.osu.domain.slider_path import build_slider_path, slider_ball_position
from src.skills.osu.env.osu_env import OsuEnv
from src.skills.osu.viewer.replay_models import ReplayFrame


try:
    import yaml  # type: ignore
except Exception:
    yaml = None


@dataclass(slots=True)
class ViewerConfig:
    window_width: int = 1600
    window_height: int = 900
    fps: int = 60
    background_dim_alpha: int = 150
    playfield_pad_x: int = 80
    playfield_pad_y: int = 60
    cursor_trail_length: int = 18
    show_follow_points: bool = True
    audio_offset_ms: float = 0.0

    combo_colors: list[tuple[int, int, int]] | None = None
    cursor_color: tuple[int, int, int] = (255, 90, 135)
    cursor_trail_color: tuple[int, int, int] = (255, 140, 170)
    slider_inner_color: tuple[int, int, int] = (20, 30, 48)
    slider_outer_color: tuple[int, int, int] = (248, 248, 252)

    burst_300_color: tuple[int, int, int] = (140, 220, 255)
    burst_100_color: tuple[int, int, int] = (130, 255, 150)
    burst_50_color: tuple[int, int, int] = (255, 225, 130)
    burst_miss_color: tuple[int, int, int] = (255, 110, 110)


def _load_viewer_config_from_yaml() -> dict:
    config_path = Path("configs/osu/viewer.yaml")
    if yaml is None or not config_path.exists():
        return {}

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class OsuViewer:
    def __init__(self, env: OsuEnv, config: ViewerConfig | None = None) -> None:
        self.env = env

        yaml_cfg = _load_viewer_config_from_yaml()
        self.config = config or ViewerConfig()
        self._apply_yaml_config(yaml_cfg)

        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.font.init()
        pygame.mixer.init()

        self.screen = pygame.display.set_mode((self.config.window_width, self.config.window_height))
        pygame.display.set_caption("Osu Viewer")
        self.clock = pygame.time.Clock()

        self.font_small = pygame.font.SysFont("arial", 22)
        self.font_mid = pygame.font.SysFont("arial", 30, bold=True)
        self.font_big = pygame.font.SysFont("arial", 42, bold=True)
        self.font_judge = pygame.font.SysFont("arial", 34, bold=True)
        self.font_circle = pygame.font.SysFont("arial", 34, bold=True)
        self.font_burst = pygame.font.SysFont("arial", 34, bold=True)
        self.font_slider_arrow = pygame.font.SysFont("arial", 24, bold=True)

        self.last_click_flash = 0.0
        self.combo_pop_timer = 0.0
        self.playfield_rect = self._compute_playfield_rect()
        self.background_surface = self._load_background_surface()
        self.music_loaded = False
        self.cursor_trail: list[tuple[int, int]] = []

        self.last_music_pos_ms: float | None = None

        self.combo_palette = self.config.combo_colors or [
            (255, 122, 147),
            (76, 132, 255),
            (255, 210, 87),
            (126, 221, 255),
        ]

        self.slider_path_cache: dict[int, object] = {}
        self.live_start_perf: float | None = None
        self.music_start_perf: float | None = None
        self.max_env_steps_per_frame: int = 8
        print("TRAIL LENGTH:", self.config.cursor_trail_length)
    def _apply_yaml_config(self, data: dict) -> None:
        for field_name in asdict(self.config).keys():
            if field_name not in data:
                continue

            value = data[field_name]

            if field_name in {
                "cursor_color",
                "cursor_trail_color",
                "slider_inner_color",
                "slider_outer_color",
                "burst_300_color",
                "burst_100_color",
                "burst_50_color",
                "burst_miss_color",
            }:
                if isinstance(value, list) and len(value) == 3:
                    setattr(self.config, field_name, tuple(int(v) for v in value))
                continue

            if field_name == "combo_colors":
                if isinstance(value, list):
                    parsed = []
                    for item in value:
                        if isinstance(item, list) and len(item) == 3:
                            parsed.append(tuple(int(v) for v in item))
                    if parsed:
                        self.config.combo_colors = parsed
                continue

            setattr(self.config, field_name, value)

    def _get_slider_path_cached(self, slider: SliderObject):
        key = id(slider)
        cached = self.slider_path_cache.get(key)
        if cached is not None:
            return cached

        path = build_slider_path(slider)
        self.slider_path_cache[key] = path
        return path

    def _compute_playfield_rect(self) -> pygame.Rect:
        avail_w = self.config.window_width - self.config.playfield_pad_x * 2
        avail_h = self.config.window_height - self.config.playfield_pad_y * 2

        scale = min(avail_w / OSU_PLAYFIELD_WIDTH, avail_h / OSU_PLAYFIELD_HEIGHT)
        w = int(OSU_PLAYFIELD_WIDTH * scale)
        h = int(OSU_PLAYFIELD_HEIGHT * scale)

        x = (self.config.window_width - w) // 2
        y = (self.config.window_height - h) // 2
        return pygame.Rect(x, y, w, h)

    def _load_background_surface(self) -> Optional[pygame.Surface]:
        bg_path = self.env.beatmap.background_path
        if bg_path is None or not bg_path.exists():
            return None

        image = pygame.image.load(str(bg_path)).convert()
        return pygame.transform.smoothscale(
            image,
            (self.config.window_width, self.config.window_height),
        )

    def _load_music(self) -> None:
        if self.music_loaded:
            return

        audio_path = self.env.beatmap.audio_path
        if audio_path is None or not audio_path.exists():
            return

        pygame.mixer.music.load(str(audio_path))
        self.music_loaded = True

    def _start_music(self) -> None:
        self._load_music()
        self.last_music_pos_ms = None
        if self.music_loaded:
            pygame.mixer.music.play()

    def _music_frame_dt_ms(self, fallback_dt_ms: float) -> float:
        if not self.music_loaded:
            return fallback_dt_ms

        pos = pygame.mixer.music.get_pos()
        if pos < 0:
            return fallback_dt_ms

        music_pos = float(pos) + float(self.config.audio_offset_ms)

        if self.last_music_pos_ms is None:
            self.last_music_pos_ms = music_pos
            return fallback_dt_ms

        delta = music_pos - self.last_music_pos_ms
        self.last_music_pos_ms = music_pos

        if delta <= 0.0:
            return fallback_dt_ms

        return max(1.0, min(40.0, delta))

    def _replay_target_time_ms(self, fallback_time_ms: float) -> float:
        if not self.music_loaded:
            return fallback_time_ms

        pos = pygame.mixer.music.get_pos()
        if pos < 0:
            return fallback_time_ms

        return float(pos) + float(self.config.audio_offset_ms)

    def _to_screen(self, x: float, y: float) -> tuple[int, int]:
        px = self.playfield_rect.x + int((x / OSU_PLAYFIELD_WIDTH) * self.playfield_rect.w)
        py = self.playfield_rect.y + int((y / OSU_PLAYFIELD_HEIGHT) * self.playfield_rect.h)
        return px, py

    def _scale_radius(self, r: float) -> int:
        return max(2, int(r * self.playfield_rect.w / OSU_PLAYFIELD_WIDTH))

    def _combo_color(self, combo_index: int) -> tuple[int, int, int]:
        return self.combo_palette[combo_index % len(self.combo_palette)]

    def _make_alpha_surface(self, w: int, h: int) -> pygame.Surface:
        return pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)

    def _draw_soft_glow(
        self,
        center: tuple[int, int],
        radius: int,
        color: tuple[int, int, int],
        strength: float = 1.0,
        steps: int = 5,
    ) -> None:
        extra = radius + 40
        surf = self._make_alpha_surface(extra * 2, extra * 2)
        cx, cy = extra, extra

        for i in range(steps, 0, -1):
            rr = radius + i * 6
            alpha = int((10 + i * 6) * strength)
            pygame.gfxdraw.filled_circle(surf, cx, cy, rr, (*color, alpha))

        self.screen.blit(surf, (center[0] - extra, center[1] - extra))

    def _draw_ring_alpha(
        self,
        center: tuple[int, int],
        radius: int,
        color: tuple[int, int, int],
        alpha: int,
        width: int = 2,
    ) -> None:
        surf = self._make_alpha_surface(radius * 2 + width * 6, radius * 2 + width * 6)
        cx = surf.get_width() // 2
        cy = surf.get_height() // 2
        pygame.draw.circle(surf, (*color, alpha), (cx, cy), radius, width=width)
        self.screen.blit(surf, (center[0] - cx, center[1] - cy))

    def _draw_filled_circle_alpha(
        self,
        center: tuple[int, int],
        radius: int,
        color: tuple[int, int, int],
        alpha: int,
    ) -> None:
        surf = self._make_alpha_surface(radius * 2 + 8, radius * 2 + 8)
        cx = surf.get_width() // 2
        cy = surf.get_height() // 2
        pygame.gfxdraw.filled_circle(surf, cx, cy, radius, (*color, alpha))
        pygame.gfxdraw.aacircle(surf, cx, cy, radius, (*color, alpha))
        self.screen.blit(surf, (center[0] - cx, center[1] - cy))

    def _draw_slider_body(
        self,
        screen_points: list[tuple[int, int]],
        combo_color: tuple[int, int, int],
        radius_px: int,
    ) -> None:
        if len(screen_points) < 2:
            return

        outer_width = max(8, radius_px * 2)
        combo_width = max(6, outer_width - 6)
        inner_width = max(4, int(outer_width * 0.72))

        tint = tuple(min(255, c + 20) for c in combo_color)

        glow_surf = self._make_alpha_surface(self.config.window_width, self.config.window_height)
        pygame.draw.lines(glow_surf, (*combo_color, 44), False, screen_points, width=outer_width + 14)
        self.screen.blit(glow_surf, (0, 0))

        pygame.draw.lines(self.screen, self.config.slider_outer_color, False, screen_points, width=outer_width)
        pygame.draw.lines(self.screen, tint, False, screen_points, width=combo_width)
        pygame.draw.lines(self.screen, self.config.slider_inner_color, False, screen_points, width=inner_width)

        highlight_width = max(2, inner_width // 4)
        pygame.draw.lines(self.screen, (70, 95, 135), False, screen_points, width=highlight_width)

        start = screen_points[0]
        end = screen_points[-1]

        for px, py in (start, end):
            pygame.draw.circle(self.screen, self.config.slider_outer_color, (px, py), outer_width // 2)
            pygame.draw.circle(self.screen, tint, (px, py), combo_width // 2)
            pygame.draw.circle(self.screen, self.config.slider_inner_color, (px, py), inner_width // 2)

    def _draw_cursor(self, cursor_x: float, cursor_y: float) -> None:
        cx, cy = self._to_screen(cursor_x, cursor_y)

        self.cursor_trail.append((cx, cy))
        if len(self.cursor_trail) > self.config.cursor_trail_length:
            self.cursor_trail.pop(0)

        # --- trail snake ---
        if len(self.cursor_trail) >= 2:
            trail_surf = self._make_alpha_surface(self.config.window_width, self.config.window_height)

            points = self.cursor_trail[:]
            total = len(points)

            for i in range(1, total):
                x1, y1 = points[i - 1]
                x2, y2 = points[i]

                t = i / max(1, total - 1)

                width = max(2, int(2 + 10 * t))
                alpha = int(10 + 90 * t)

                color = (*self.config.cursor_trail_color, alpha)
                pygame.draw.line(trail_surf, color, (x1, y1), (x2, y2), width)

                # мягкие круглые стыки, чтобы линия не ломалась
                r = max(1, width // 2)
                pygame.gfxdraw.filled_circle(trail_surf, x2, y2, r, color)
                pygame.gfxdraw.aacircle(trail_surf, x2, y2, r, color)

            # дополнительный мягкий glow у хвоста
            for i in range(2, total, 2):
                tx, ty = points[i]
                t = i / max(1, total - 1)
                rr = max(2, int(4 + 8 * t))
                alpha = int(6 + 28 * t)
                pygame.gfxdraw.filled_circle(
                    trail_surf,
                    tx,
                    ty,
                    rr,
                    (*self.config.cursor_trail_color, alpha),
                )

            self.screen.blit(trail_surf, (0, 0))

        # --- main cursor glow ---
        self._draw_soft_glow((cx, cy), 12, self.config.cursor_color, strength=1.2, steps=5)

        # outer white ring
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 14, width=3)

        # main cursor body
        pygame.draw.circle(self.screen, self.config.cursor_color, (cx, cy), 9)

        # inner highlight
        pygame.draw.circle(self.screen, (255, 220, 230), (cx, cy), 5)

        # center white dot
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 2)

        # --- click flash ---
        if self.last_click_flash > 0.0:
            k = self.last_click_flash / 0.12

            # outer expanding ring
            self._draw_ring_alpha(
                (cx, cy),
                int(18 + 42 * k),
                (255, 255, 255),
                int(180 * k),
                width=3,
            )

            # colored ring
            self._draw_ring_alpha(
                (cx, cy),
                int(10 + 24 * k),
                self.config.cursor_trail_color,
                int(140 * k),
                width=2,
            )

            # little flash core
            self._draw_filled_circle_alpha(
                (cx, cy),
                int(8 + 8 * k),
                (255, 255, 255),
                int(80 * k),
            )

    def _draw_burst(self, label: str, x: int, y: int, age_ms: float) -> None:
        life_ms = 680.0
        if age_ms < 0 or age_ms > life_ms:
            return

        t = age_ms / life_ms
        alpha = int(255 * (1.0 - t))
        scale = 0.72 + 0.42 * (1.0 - math.exp(-5.0 * t))
        y_offset = int(24 * t)

        if label == "300":
            color = self.config.burst_300_color
        elif label == "100":
            color = self.config.burst_100_color
        elif label == "50":
            color = self.config.burst_50_color
        else:
            color = self.config.burst_miss_color

        base = self.font_burst.render(label, True, color)
        shadow = self.font_burst.render(label, True, (16, 18, 22))

        sw = max(1, int(base.get_width() * scale))
        sh = max(1, int(base.get_height() * scale))

        base = pygame.transform.smoothscale(base, (sw, sh))
        shadow = pygame.transform.smoothscale(shadow, (sw, sh))

        base.set_alpha(alpha)
        shadow.set_alpha(max(0, int(alpha * 0.7)))

        rect = base.get_rect(center=(x, y - y_offset))
        shadow_rect = shadow.get_rect(center=(x + 2, y + 2 - y_offset))

        self.screen.blit(shadow, shadow_rect)
        self.screen.blit(base, rect)

    def _combo_scale(self) -> float:
        if self.combo_pop_timer <= 0.0:
            return 1.0
        k = self.combo_pop_timer / 0.15
        return 1.0 + 0.22 * k

    def _draw_hud(self, info: dict) -> None:
        title = f"{self.env.beatmap.artist} - {self.env.beatmap.title} [{self.env.beatmap.version}]"
        title_text = self.font_mid.render(title, True, (255, 255, 255))
        self.screen.blit(title_text, (24, 20))

        combo_value = f"{info.get('combo', 0)}x"
        combo_surf = self.font_big.render(combo_value, True, (255, 255, 255))
        combo_scale = self._combo_scale()
        if abs(combo_scale - 1.0) > 1e-4:
            combo_surf = pygame.transform.smoothscale(
                combo_surf,
                (
                    max(1, int(combo_surf.get_width() * combo_scale)),
                    max(1, int(combo_surf.get_height() * combo_scale)),
                ),
            )
        self.screen.blit(combo_surf, (24, 64))

        acc = info.get("accuracy", 1.0) * 100.0
        acc_text = self.font_mid.render(f"Acc {acc:05.2f}%", True, (255, 255, 255))
        self.screen.blit(acc_text, (24, 114))

        hit_text = self.font_small.render(
            f"Hits {info.get('hit_count', 0)} | Miss {info.get('miss_count', 0)}",
            True,
            (220, 230, 255),
        )
        self.screen.blit(hit_text, (24, 154))

        judge_text = self.font_small.render(
            f"Last: {info.get('judgement', 'none')}",
            True,
            (255, 220, 180),
        )
        self.screen.blit(judge_text, (24, 186))

        time_text = self.font_small.render(
            f"Time {info.get('time_ms', 0.0):8.1f} ms",
            True,
            (200, 210, 230),
        )
        self.screen.blit(time_text, (24, 218))

    def _draw_judgement_popups(self, now_ms: float) -> None:
        popups = self.env.consume_recent_judgements(now_ms)
        for popup in popups:
            self._draw_single_popup(
                popup["judgement"],
                popup["time_ms"],
                popup.get("score_value", 0),
                popup.get("popup_x"),
                popup.get("popup_y"),
            )

    def _draw_single_popup(
        self,
        judgement: str,
        event_time_ms: float,
        score_value: int = 0,
        popup_x: float | None = None,
        popup_y: float | None = None,
    ) -> None:
        age_ms = self.env.time_ms - event_time_ms
        if age_ms < 0 or age_ms > 680.0:
            return

        if popup_x is None or popup_y is None:
            sx, sy = self.playfield_rect.centerx, self.playfield_rect.centery
        else:
            sx, sy = self._to_screen(popup_x, popup_y)

        if score_value in (300, 100, 50):
            label = str(score_value)
        elif judgement == "miss":
            label = "miss"
        else:
            return

        self._draw_burst(label, sx, sy - 28, age_ms)

    def _draw_follow_points(self, visible_objects) -> None:
        if not self.config.show_follow_points or len(visible_objects) < 2:
            return

        circle_radius_px = self._scale_radius(osu_circle_radius(self.env.beatmap.difficulty.cs))

        for a, b in zip(visible_objects[:-1], visible_objects[1:]):
            ax, ay = self._object_anchor(a)
            bx, by = self._object_anchor(b)

            start = self._to_screen(ax, ay)
            end = self._to_screen(bx, by)

            dx = end[0] - start[0]
            dy = end[1] - start[1]
            dist_px = math.hypot(dx, dy)
            if dist_px < circle_radius_px * 2.4:
                continue

            steps = max(2, int(dist_px / 42))
            follow_surf = self._make_alpha_surface(self.config.window_width, self.config.window_height)

            for i in range(1, steps):
                t = i / steps
                px = int(start[0] + dx * t)
                py = int(start[1] + dy * t)
                r = max(2, int(2 + 2 * (1.0 - abs(0.5 - t))))
                alpha = 70
                pygame.gfxdraw.filled_circle(follow_surf, px, py, r, (255, 255, 255, alpha))
                pygame.gfxdraw.aacircle(follow_surf, px, py, r, (255, 255, 255, alpha))

            self.screen.blit(follow_surf, (0, 0))

    def _draw_circle_number(self, sx: int, sy: int, number: int) -> None:
        text = self.font_circle.render(str(number), True, (255, 255, 255))
        rect = text.get_rect(center=(sx, sy))
        shadow = self.font_circle.render(str(number), True, (20, 20, 25))
        shadow_rect = shadow.get_rect(center=(sx + 2, sy + 2))
        self.screen.blit(shadow, shadow_rect)
        self.screen.blit(text, rect)

    def _draw_hit_circle(
        self,
        x: float,
        y: float,
        time_to_hit: float,
        radius_px: int,
        combo_index: int = 0,
        number: int = 1,
    ) -> None:
        sx, sy = self._to_screen(x, y)
        combo_color = self._combo_color(combo_index)

        preempt_ms = ar_to_preempt_ms(self.env.beatmap.difficulty.ar)
        clamped = max(0.0, min(1.0, time_to_hit / preempt_ms))
        approach_scale = 1.0 + clamped * 3.0
        approach_radius = max(radius_px + 2, int(radius_px * approach_scale))
        approach_alpha = int(36 + 126 * clamped)

        self._draw_ring_alpha((sx, sy), approach_radius, combo_color, approach_alpha, width=3)
        self._draw_soft_glow((sx, sy), radius_px, combo_color, strength=0.8, steps=4)

        pygame.draw.circle(self.screen, (248, 248, 250), (sx, sy), radius_px)
        pygame.draw.circle(self.screen, combo_color, (sx, sy), max(2, radius_px - 4))

        center_color = (
            max(18, int(combo_color[0] * 0.28)),
            max(18, int(combo_color[1] * 0.28)),
            max(22, int(combo_color[2] * 0.28)),
        )
        pygame.draw.circle(self.screen, center_color, (sx, sy), max(2, int(radius_px * 0.62)))
        self._draw_filled_circle_alpha((sx, sy - radius_px // 6), int(radius_px * 0.45), (255, 255, 255), 50)
        pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), radius_px, width=2)

        self._draw_circle_number(sx, sy, number)

    def _draw_slider_repeat_arrow(
        self,
        x: int,
        y: int,
        direction_angle: float,
    ) -> None:
        arrow_text = self.font_slider_arrow.render("»", True, (255, 255, 255))
        arrow_text = pygame.transform.rotate(arrow_text, -math.degrees(direction_angle))
        rect = arrow_text.get_rect(center=(x, y))
        self.screen.blit(arrow_text, rect)

    def _draw_slider_ticks(
        self,
        path,
        slider: SliderObject,
        start_time_ms: float,
        end_time_ms: float,
        radius_px: int,
    ) -> None:
        total_ticks = max(0, int(math.floor(max(0.0, self.env.beatmap.difficulty.slider_tick_rate - 0.01))))
        if total_ticks <= 0:
            return

        span_duration = (end_time_ms - start_time_ms) / max(1, slider.repeats)
        tick_radius = max(3, radius_px // 8)

        for span_idx in range(slider.repeats):
            reverse = (span_idx % 2) == 1
            for i in range(1, total_ticks + 1):
                frac = i / (total_ticks + 1)
                local = 1.0 - frac if reverse else frac
                tx, ty = path.position_at_progress(local)
                sx, sy = self._to_screen(tx, ty)
                pygame.draw.circle(self.screen, (255, 232, 160), (sx, sy), tick_radius)
                pygame.draw.circle(self.screen, (255, 255, 255), (sx, sy), tick_radius, width=1)

    def _draw_slider_follow_circle(self, current_time_ms: float, cursor_x: float, cursor_y: float, click_down: bool) -> None:
        if self.env.judge.active_slider is None:
            return

        ball = self.env.judge.current_slider_ball_position(current_time_ms)
        if ball is None:
            return

        bx, by = ball
        sx, sy = self._to_screen(bx, by)
        follow_radius_osu = self.env.judge.radius * 1.4
        follow_radius_px = self._scale_radius(follow_radius_osu)

        near = click_down and distance(cursor_x, cursor_y, bx, by) <= follow_radius_osu

        if near:
            color = (255, 255, 255)
            alpha = 120
            glow_color = (255, 255, 255)
        else:
            color = (200, 210, 230)
            alpha = 48
            glow_color = (150, 180, 220)

        self._draw_soft_glow((sx, sy), max(10, follow_radius_px - 2), glow_color, strength=0.5, steps=3)
        self._draw_ring_alpha((sx, sy), follow_radius_px, color, alpha, width=3)

    def _draw_slider(
        self,
        slider: SliderObject,
        time_to_hit: float,
        radius_px: int,
        current_time_ms: float,
    ) -> None:
        path = self._get_slider_path_cached(slider)
        screen_points = [self._to_screen(x, y) for x, y in path.sampled_points]
        combo_color = self._combo_color(slider.combo_index)

        if len(screen_points) >= 2:
            self._draw_slider_body(screen_points, combo_color, radius_px)

        total_duration = slider_duration_ms(self.env.beatmap, slider)
        start_time = slider.time_ms
        end_time = slider.time_ms + total_duration

        self._draw_slider_ticks(path, slider, start_time, end_time, radius_px)

        self._draw_hit_circle(
            x=slider.x,
            y=slider.y,
            time_to_hit=time_to_hit,
            radius_px=radius_px,
            combo_index=slider.combo_index,
            number=slider.combo_number,
        )

        tail_progress = 0.0 if (slider.repeats % 2 == 0) else 1.0
        tail_x, tail_y = path.position_at_progress(tail_progress)
        tail_sx, tail_sy = self._to_screen(tail_x, tail_y)
        pygame.draw.circle(self.screen, (248, 248, 250), (tail_sx, tail_sy), radius_px)
        pygame.draw.circle(self.screen, combo_color, (tail_sx, tail_sy), max(2, radius_px - 4))
        pygame.draw.circle(self.screen, self.config.slider_inner_color, (tail_sx, tail_sy), max(2, int(radius_px * 0.62)))
        pygame.draw.circle(self.screen, (255, 255, 255), (tail_sx, tail_sy), radius_px, width=2)

        if slider.repeats > 1 and len(screen_points) >= 3:
            prev_x, prev_y = screen_points[-2]
            angle_tail = math.atan2(tail_sy - prev_y, tail_sx - prev_x)
            self._draw_slider_repeat_arrow(tail_sx, tail_sy, angle_tail)

            if slider.repeats > 2:
                head_sx, head_sy = self._to_screen(slider.x, slider.y)
                next_x, next_y = screen_points[min(1, len(screen_points) - 1)]
                angle_head = math.atan2(head_sy - next_y, head_sx - next_x)
                self._draw_slider_repeat_arrow(head_sx, head_sy, angle_head)

        ball_x, ball_y = slider_ball_position(
            path=path,
            repeats=slider.repeats,
            start_time_ms=start_time,
            end_time_ms=end_time,
            current_time_ms=current_time_ms,
        )
        bx, by = self._to_screen(ball_x, ball_y)

        self._draw_soft_glow((bx, by), max(8, radius_px // 2), (255, 255, 255), strength=0.75, steps=4)
        pygame.draw.circle(self.screen, (255, 255, 255), (bx, by), max(9, radius_px // 2))
        pygame.draw.circle(self.screen, combo_color, (bx, by), max(5, radius_px // 3))
        pygame.draw.circle(self.screen, (255, 255, 255), (bx, by), max(9, radius_px // 2), width=2)

    def _draw_spinner(self, spinner, time_ms: float) -> None:
        cx, cy = self._to_screen(256.0, 192.0)
        big_r = self._scale_radius(100)

        self._draw_soft_glow((cx, cy), big_r, (120, 170, 255), strength=0.6, steps=5)
        pygame.draw.circle(self.screen, (240, 245, 255), (cx, cy), big_r, width=5)

        if spinner.end_time_ms > spinner.time_ms:
            progress = (time_ms - spinner.time_ms) / (spinner.end_time_ms - spinner.time_ms)
            progress = max(0.0, min(1.0, progress))
        else:
            progress = 0.0

        arc_rect = pygame.Rect(cx - big_r, cy - big_r, big_r * 2, big_r * 2)
        pygame.draw.arc(
            self.screen,
            (255, 210, 120),
            arc_rect,
            -math.pi / 2,
            -math.pi / 2 + 2 * math.pi * progress,
            width=8,
        )

        inner_r = int(big_r * 0.5)
        pygame.draw.circle(self.screen, (40, 55, 84), (cx, cy), inner_r)
        pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), inner_r, width=3)

    def _draw_background(self) -> None:
        if self.background_surface is not None:
            self.screen.blit(self.background_surface, (0, 0))
        else:
            self.screen.fill((12, 16, 28))

        dim = pygame.Surface((self.config.window_width, self.config.window_height), pygame.SRCALPHA)
        dim.fill((0, 0, 0, self.config.background_dim_alpha))
        self.screen.blit(dim, (0, 0))

    def run(self, policy_fn: Callable) -> None:
        obs = self.env.reset()
        self.cursor_trail.clear()
        self.combo_pop_timer = 0.0
        self.slider_path_cache.clear()

        self.live_start_perf = time.perf_counter()
        self._start_music()
        self.music_start_perf = time.perf_counter()

        final_info: dict | None = None

        while True:
            dt_ms_fallback = self.clock.tick(self.config.fps)
            dt_sec = dt_ms_fallback / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

            if self.env.done:
                final_info = self.env.last_info or {}
                break

            if self.live_start_perf is None:
                target_time_ms = self.env.time_ms + dt_ms_fallback
            else:
                elapsed_ms = (time.perf_counter() - self.live_start_perf) * 1000.0
                target_time_ms = elapsed_ms + float(self.config.audio_offset_ms)

            steps = 0
            while self.env.time_ms + self.env.dt_ms <= target_time_ms and steps < self.max_env_steps_per_frame:
                action = policy_fn(obs)
                step = self.env.step(action)
                obs = step.observation

                if action.click_strength >= self.env.click_threshold:
                    self.last_click_flash = 0.12

                if step.info.get("score_value", 0) > 0:
                    self.combo_pop_timer = 0.15

                steps += 1

                if self.env.done:
                    break

            self.last_click_flash = max(0.0, self.last_click_flash - dt_sec)
            self.combo_pop_timer = max(0.0, self.combo_pop_timer - dt_sec)

            self.draw(obs, self.env.last_info or {})

        if self.music_loaded:
            pygame.mixer.music.stop()

        self._results_loop(final_info or {})

    def play_replay(self, frames: list[ReplayFrame]) -> None:
        self.cursor_trail.clear()
        self.combo_pop_timer = 0.0
        self.slider_path_cache.clear()

        if not frames:
            return

        self._start_music()
        replay_start_perf = time.perf_counter()

        idx = 0

        while True:
            dt_ms = self.clock.tick(self.config.fps)
            dt_sec = dt_ms / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

            elapsed_ms = (time.perf_counter() - replay_start_perf) * 1000.0
            target_time_ms = elapsed_ms + float(self.config.audio_offset_ms)

            while idx + 1 < len(frames) and frames[idx + 1].time_ms <= target_time_ms:
                idx += 1

            frame = frames[idx]
            self.env.time_ms = frame.time_ms

            if frame.score_value > 0:
                self.combo_pop_timer = 0.15

            self.last_click_flash = max(0.0, self.last_click_flash - dt_sec)
            self.combo_pop_timer = max(0.0, self.combo_pop_timer - dt_sec)

            self.draw_replay_frame(frame)

            if idx >= len(frames) - 1 and target_time_ms >= frames[-1].time_ms:
                break

        if self.music_loaded:
            pygame.mixer.music.stop()

        final_info = {
            "accuracy": frames[-1].accuracy if frames else 1.0,
            "max_combo": max((f.combo for f in frames), default=0),
        }
        self._results_loop(final_info)

    def _object_anchor(self, obj) -> tuple[float, float]:
        if obj.kind == HitObjectType.CIRCLE:
            return obj.circle.x, obj.circle.y
        if obj.kind == HitObjectType.SLIDER:
            return obj.slider.x, obj.slider.y
        return obj.spinner.x, obj.spinner.y

    def draw(self, obs, info: dict) -> None:
        self._draw_background()

        radius_osu = osu_circle_radius(self.env.beatmap.difficulty.cs)
        radius_px = self._scale_radius(radius_osu)

        visible_objects = self.env.get_visible_objects()
        self._draw_follow_points(visible_objects)

        for obj in visible_objects:
            if obj.kind == HitObjectType.CIRCLE:
                time_to_hit = obj.circle.time_ms - obs.time_ms
                self._draw_hit_circle(
                    x=obj.circle.x,
                    y=obj.circle.y,
                    time_to_hit=time_to_hit,
                    radius_px=radius_px,
                    combo_index=obj.circle.combo_index,
                    number=obj.circle.combo_number,
                )
            elif obj.kind == HitObjectType.SLIDER:
                time_to_hit = obj.slider.time_ms - obs.time_ms
                self._draw_slider(
                    slider=obj.slider,
                    time_to_hit=time_to_hit,
                    radius_px=radius_px,
                    current_time_ms=obs.time_ms,
                )
            elif obj.kind == HitObjectType.SPINNER:
                self._draw_spinner(obj.spinner, obs.time_ms)

        self._draw_slider_follow_circle(obs.time_ms, obs.cursor_x, obs.cursor_y, info.get("click_down", False))
        self._draw_cursor(obs.cursor_x, obs.cursor_y)
        self._draw_judgement_popups(obs.time_ms)
        self._draw_hud(info)
        pygame.display.flip()

    def draw_replay_frame(self, frame: ReplayFrame) -> None:
        self._draw_background()

        radius_osu = osu_circle_radius(self.env.beatmap.difficulty.cs)
        radius_px = self._scale_radius(radius_osu)

        visible_objects = self.env.get_visible_objects()
        self._draw_follow_points(visible_objects)

        for obj in visible_objects:
            if obj.kind == HitObjectType.CIRCLE:
                time_to_hit = obj.circle.time_ms - frame.time_ms
                self._draw_hit_circle(
                    obj.circle.x,
                    obj.circle.y,
                    time_to_hit,
                    radius_px,
                    combo_index=obj.circle.combo_index,
                    number=obj.circle.combo_number,
                )
            elif obj.kind == HitObjectType.SLIDER:
                time_to_hit = obj.slider.time_ms - frame.time_ms
                self._draw_slider(obj.slider, time_to_hit, radius_px, frame.time_ms)
            elif obj.kind == HitObjectType.SPINNER:
                self._draw_spinner(obj.spinner, frame.time_ms)

        self._draw_slider_follow_circle(frame.time_ms, frame.cursor_x, frame.cursor_y, frame.click_down)
        self._draw_cursor(frame.cursor_x, frame.cursor_y)

        info = {
            "combo": frame.combo,
            "accuracy": frame.accuracy,
            "hit_count": 0,
            "miss_count": 0,
            "judgement": frame.judgement,
            "time_ms": frame.time_ms,
        }
        self._draw_hud(info)

        if frame.judgement != "none":
            self._draw_single_popup(
                frame.judgement,
                frame.time_ms,
                frame.score_value,
                frame.popup_x,
                frame.popup_y,
            )

        pygame.display.flip()

    def _results_loop(self, info: dict) -> None:
        while True:
            self.clock.tick(self.config.fps)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit(0)

            self._draw_background()
            self.draw_done(info)
            pygame.display.flip()

    def draw_done(self, info: dict) -> None:
        overlay = pygame.Surface((self.config.window_width, self.config.window_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        title = self.font_big.render("Replay ended!", True, (255, 255, 255))
        acc = self.font_mid.render(
            f"Final Acc: {info.get('accuracy', 1.0) * 100.0:05.2f}%",
            True,
            (255, 255, 255),
        )
        combo = self.font_mid.render(
            f"Max Combo: {info.get('max_combo', 0)}x",
            True,
            (255, 255, 255),
        )

        title_rect = title.get_rect(center=(self.config.window_width // 2, self.config.window_height // 2 - 40))
        acc_rect = acc.get_rect(center=(self.config.window_width // 2, self.config.window_height // 2 + 10))
        combo_rect = combo.get_rect(center=(self.config.window_width // 2, self.config.window_height // 2 + 50))

        self.screen.blit(title, title_rect)
        self.screen.blit(acc, acc_rect)
        self.screen.blit(combo, combo_rect)