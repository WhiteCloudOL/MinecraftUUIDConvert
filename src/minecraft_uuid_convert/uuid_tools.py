"""Minecraft Java Edition UUID parsing and generation helpers."""

from __future__ import annotations

import hashlib
import re
import uuid

UUID_PATTERN = re.compile(
    r"(?<![0-9a-f])"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}"
    r"(?![0-9a-f])",
    re.IGNORECASE,
)
COMPACT_UUID_PATTERN = re.compile(
    r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])",
    re.IGNORECASE,
)
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{1,16}$")


def normalize_uuid(value: str) -> str:
    """Return a UUID in Minecraft's canonical hyphenated lowercase form."""
    return str(uuid.UUID(value.strip()))


def offline_uuid(username: str) -> str:
    """Calculate the Java Edition offline-mode UUID for ``username``.

    Minecraft-compatible servers use Java's ``UUID.nameUUIDFromBytes`` over
    the UTF-8 bytes of ``OfflinePlayer:<username>``. That is an MD5-based
    version 3 UUID without an RFC namespace UUID.
    """
    if not username:
        raise ValueError("玩家名不能为空")

    digest = bytearray(hashlib.md5(f"OfflinePlayer:{username}".encode()).digest())
    digest[6] = (digest[6] & 0x0F) | 0x30
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def uuid_version(value: str) -> int | None:
    """Return the UUID version, or ``None`` when ``value`` is invalid."""
    try:
        return uuid.UUID(value).version
    except ValueError:
        return None


def find_uuids(text: str) -> set[str]:
    """Return canonical hyphenated and compact UUIDs found in text."""
    matches = [*UUID_PATTERN.finditer(text), *COMPACT_UUID_PATTERN.finditer(text)]
    return {normalize_uuid(match.group(0)) for match in matches}


def replace_uuid_forms(text: str, mapping: dict[str, str]) -> str:
    """Replace canonical, compact, and FTB player-name UUID forms."""
    updated = text
    for source_uuid, target_uuid in mapping.items():
        source = normalize_uuid(source_uuid)
        target = normalize_uuid(target_uuid)
        replacements = (
            (re.escape(source), target),
            (re.escape(source.replace("-", "")), target.replace("-", "")),
            (rf"#{re.escape(source[:8])}(?![0-9a-f])", f"#{target[:8]}"),
        )
        for pattern, replacement in replacements:
            updated = re.sub(pattern, replacement, updated, flags=re.IGNORECASE)
    return updated
