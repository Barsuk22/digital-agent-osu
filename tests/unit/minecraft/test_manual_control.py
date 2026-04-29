from __future__ import annotations

import pytest

from src.skills.minecraft.actions import build_manual_action, manual_action_specs


def test_manual_action_specs_cover_phase_b1_controls() -> None:
    specs = manual_action_specs(duration_ms=90, look_degrees=10.0, chat_message="hi")
    expected = {
        "noop",
        "move_forward",
        "move_back",
        "move_left",
        "move_right",
        "jump",
        "sneak",
        "sprint",
        "look_left",
        "look_right",
        "look_up",
        "look_down",
        "chat",
        "stop",
    }
    assert expected.issubset(specs)
    assert specs["move_forward"].action.command == "move_forward"
    assert specs["move_forward"].action.forward == 1.0
    assert specs["move_forward"].action.duration_ms == 90
    assert specs["look_left"].action.command == "look_delta"
    assert specs["look_left"].action.camera_yaw_delta == -10.0
    assert specs["chat"].action.chat_message == "hi"


def test_build_manual_action_rejects_unknown_action() -> None:
    with pytest.raises(ValueError):
        build_manual_action("dig_to_bedrock")
