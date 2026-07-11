"""Small client for public Minecraft profile lookup services."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from minecraft_uuid_convert.uuid_tools import normalize_uuid


class ProfileLookupError(RuntimeError):
    """Raised when a player profile cannot be resolved."""


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    """A current Minecraft Java player identity."""

    name: str
    uuid: str


class MinecraftProfileClient:
    """Resolve current Java Edition names and online UUIDs."""

    def __init__(self, *, timeout: float = 8.0) -> None:
        self.timeout = timeout

    def by_name(self, username: str) -> PlayerProfile:
        """Resolve a current player name through Minecraft Services."""
        safe_name = quote(username.strip(), safe="")
        payload = self._get_json(
            "https://api.minecraftservices.com/"
            f"minecraft/profile/lookup/name/{safe_name}"
        )
        return self._profile_from_payload(payload, username)

    def by_uuid(self, player_uuid: str) -> PlayerProfile:
        """Resolve an online UUID through Mojang's session server."""
        canonical = normalize_uuid(player_uuid)
        payload = self._get_json(
            "https://sessionserver.mojang.com/session/minecraft/profile/"
            f"{canonical.replace('-', '')}"
        )
        return self._profile_from_payload(payload, canonical)

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "MinecraftUUIDConvert/1.0",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                data = json.load(response)
        except HTTPError as exc:
            if exc.code in {204, 404}:
                raise ProfileLookupError("未找到对应的正版玩家档案") from exc
            raise ProfileLookupError(f"玩家服务返回 HTTP {exc.code}") from exc
        except (URLError, TimeoutError) as exc:
            raise ProfileLookupError(f"无法连接玩家服务：{exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProfileLookupError("玩家服务返回了无法解析的数据") from exc

        if not isinstance(data, dict):
            raise ProfileLookupError("玩家服务返回格式异常")
        return data

    @staticmethod
    def _profile_from_payload(
        payload: dict[str, Any],
        requested_value: str,
    ) -> PlayerProfile:
        raw_id = payload.get("id")
        raw_name = payload.get("name")
        if not isinstance(raw_id, str) or not isinstance(raw_name, str):
            raise ProfileLookupError(f"{requested_value} 的玩家档案不完整")
        try:
            player_uuid = normalize_uuid(raw_id)
        except ValueError as exc:
            raise ProfileLookupError("玩家服务返回了无效 UUID") from exc
        return PlayerProfile(name=raw_name, uuid=player_uuid)
