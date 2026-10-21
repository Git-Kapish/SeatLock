"""Lua scripts for atomic Redis concurrency operations."""

from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent

ACQUIRE_HOLDS_LUA: str = (_SCRIPTS_DIR / "acquire_holds.lua").read_text(encoding="utf-8")
RELEASE_HOLDS_LUA: str = (_SCRIPTS_DIR / "release_holds.lua").read_text(encoding="utf-8")

__all__ = ["ACQUIRE_HOLDS_LUA", "RELEASE_HOLDS_LUA"]
