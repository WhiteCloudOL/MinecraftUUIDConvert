"""Parsers for Minecraft and mod-provided player cache files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from minecraft_uuid_convert.uuid_tools import normalize_uuid, offline_uuid


class CacheFormatError(ValueError):
    """Raised when a cache file does not match a supported structure."""


@dataclass(frozen=True, slots=True)
class PlayerCache:
    """Normalized player-name mappings loaded from one cache file."""

    uuid_to_name: dict[str, str]
    name_to_uuid: dict[str, str]

    def name_for_uuid(self, player_uuid: str) -> str | None:
        """Resolve an exact or calculated offline UUID to a player name."""
        canonical = normalize_uuid(player_uuid)
        exact = self.uuid_to_name.get(canonical)
        if exact is not None:
            return exact
        return next(
            (name for name in self.name_to_uuid if offline_uuid(name) == canonical),
            None,
        )


def load_player_cache(path: Path) -> PlayerCache:
    """Load ``usercache.json`` or ``usernamecache.json`` automatically."""
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        raise CacheFormatError(f"无法读取缓存文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise CacheFormatError(f"缓存文件不是有效 JSON：{exc}") from exc

    pairs: list[tuple[str, str]] = []
    if isinstance(raw, dict):
        pairs = [(str(player_uuid), str(name)) for player_uuid, name in raw.items()]
    elif isinstance(raw, list):
        for index, item in enumerate(raw, start=1):
            if not isinstance(item, dict) or "uuid" not in item or "name" not in item:
                raise CacheFormatError(f"缓存第 {index} 项缺少 name 或 uuid")
            pairs.append((str(item["uuid"]), str(item["name"])))
    else:
        raise CacheFormatError("缓存顶层必须是对象或数组")

    uuid_to_name: dict[str, str] = {}
    name_to_uuid: dict[str, str] = {}
    for raw_uuid, raw_name in pairs:
        name = raw_name.strip()
        if not name:
            continue
        try:
            player_uuid = normalize_uuid(raw_uuid)
        except ValueError as exc:
            raise CacheFormatError(f"玩家 {name} 的 UUID 无效：{raw_uuid}") from exc
        uuid_to_name[player_uuid] = name
        name_to_uuid[name] = player_uuid

    if not uuid_to_name:
        raise CacheFormatError("缓存中没有有效的玩家记录")
    return PlayerCache(uuid_to_name=uuid_to_name, name_to_uuid=name_to_uuid)
