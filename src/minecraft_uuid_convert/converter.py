"""Directory conversion engine for Minecraft player UUID migrations."""

from __future__ import annotations

import logging
import shutil
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from minecraft_uuid_convert.cache import PlayerCache
from minecraft_uuid_convert.services import (
    MinecraftProfileClient,
    ProfileLookupError,
)
from minecraft_uuid_convert.uuid_tools import find_uuids, normalize_uuid, offline_uuid

TEXT_SUFFIXES = {
    ".cfg",
    ".conf",
    ".json",
    ".json5",
    ".properties",
    ".snbt",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
ProgressCallback = Callable[[str], None]


class ConversionMode(StrEnum):
    """Supported migration directions."""

    ONLINE_TO_OFFLINE = "online-to-offline"
    OFFLINE_TO_ONLINE = "offline-to-online"

    @property
    def source_version(self) -> int:
        """Return the expected UUID version for this migration source."""
        return 4 if self is self.ONLINE_TO_OFFLINE else 3

    @property
    def label(self) -> str:
        """Return a concise Chinese label for presentation."""
        if self is self.ONLINE_TO_OFFLINE:
            return "正版 UUID → 离线 UUID"
        return "离线 UUID → 正版 UUID"


@dataclass(frozen=True, slots=True)
class ConversionOptions:
    """Input and behavior settings for one conversion run."""

    input_dir: Path
    output_dir: Path
    logs_dir: Path
    mode: ConversionMode
    cache: PlayerCache | None = None
    use_network: bool = True
    replace_text_references: bool = True
    recursive: bool = True


@dataclass(slots=True)
class ConversionResult:
    """Summary of a completed non-destructive conversion run."""

    total_files: int = 0
    copied_files: int = 0
    renamed_files: int = 0
    modified_text_files: int = 0
    resolved_players: dict[str, tuple[str, str]] = field(default_factory=dict)
    unresolved: dict[str, str] = field(default_factory=dict)
    collisions: list[str] = field(default_factory=list)
    log_file: Path | None = None

    @property
    def changed_files(self) -> int:
        """Return the number of files changed by name or text content."""
        return self.renamed_files + self.modified_text_files


class ConversionError(RuntimeError):
    """Raised when a conversion cannot safely start or finish."""


class UUIDResolver:
    """Resolve only UUIDs that match the selected migration direction."""

    def __init__(
        self,
        mode: ConversionMode,
        *,
        cache: PlayerCache | None,
        use_network: bool,
        client: MinecraftProfileClient | None = None,
    ) -> None:
        self.mode = mode
        self.cache = cache
        self.use_network = use_network
        self.client = client or MinecraftProfileClient()

    def resolve(self, source_uuid: str) -> tuple[str, str]:
        """Return ``(username, target_uuid)`` for one source UUID."""
        canonical = normalize_uuid(source_uuid)
        parsed = uuid.UUID(canonical)
        if parsed.version != self.mode.source_version:
            raise ProfileLookupError(
                f"UUID v{parsed.version} 不属于“{self.mode.label}”的源类型"
            )

        username = self.cache.name_for_uuid(canonical) if self.cache else None
        cached_target = self._cached_target(username) if username else None

        if self.mode is ConversionMode.ONLINE_TO_OFFLINE:
            if username is None:
                self._require_network("缓存中没有该正版 UUID")
                username = self.client.by_uuid(canonical).name
            return username, offline_uuid(username)

        if username is None:
            raise ProfileLookupError("离线 UUID 不可逆；缓存中没有对应玩家名")
        if cached_target is not None:
            return username, cached_target
        self._require_network("缓存只提供了玩家名或离线 UUID")
        return username, self.client.by_name(username).uuid

    def _cached_target(self, username: str | None) -> str | None:
        if self.cache is None or username is None:
            return None
        candidate = self.cache.name_to_uuid.get(username)
        if candidate is None:
            return None
        expected_version = 3 if self.mode is ConversionMode.ONLINE_TO_OFFLINE else 4
        if uuid.UUID(candidate).version == expected_version:
            return candidate
        return None

    def _require_network(self, reason: str) -> None:
        if not self.use_network:
            raise ProfileLookupError(f"{reason}，且已关闭在线查询")


def convert_directory(
    options: ConversionOptions,
    *,
    progress: ProgressCallback | None = None,
    client: MinecraftProfileClient | None = None,
) -> ConversionResult:
    """Mirror a directory and replace resolvable player UUID references.

    Source files are never modified. Every input file is copied to the output;
    unresolved UUIDs remain byte-for-byte unchanged.
    """
    _validate_paths(options.input_dir, options.output_dir)
    files = list(_iter_files(options.input_dir, recursive=options.recursive))
    result = ConversionResult(total_files=len(files))
    logger, handler, log_file = _create_run_logger(options.logs_dir)
    result.log_file = log_file
    notify = progress or (lambda _message: None)

    try:
        logger.info("开始转换：%s", options.mode.label)
        logger.info("输入：%s", options.input_dir)
        logger.info("输出：%s", options.output_dir)
        notify(f"发现 {len(files)} 个文件，正在识别玩家 UUID…")

        candidates = _collect_candidates(
            files,
            replace_text=options.replace_text_references,
        )
        resolver = UUIDResolver(
            options.mode,
            cache=options.cache,
            use_network=options.use_network,
            client=client,
        )
        mapping: dict[str, str] = {}
        for index, source_uuid in enumerate(sorted(candidates), start=1):
            try:
                username, target_uuid = resolver.resolve(source_uuid)
            except ProfileLookupError as exc:
                result.unresolved[source_uuid] = str(exc)
                logger.warning("未转换 %s：%s", source_uuid, exc)
            else:
                mapping[source_uuid] = target_uuid
                result.resolved_players[source_uuid] = (username, target_uuid)
                logger.info(
                    "解析玩家 %s：%s -> %s",
                    username,
                    source_uuid,
                    target_uuid,
                )
            notify(f"解析 UUID {index}/{len(candidates)}")

        options.output_dir.mkdir(parents=True, exist_ok=True)
        for index, source in enumerate(files, start=1):
            relative = source.relative_to(options.input_dir)
            target_relative = _replace_path_uuids(relative, mapping)
            target = options.output_dir / target_relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                collision_target = _unique_collision_path(target)
                preserved_relative = collision_target.relative_to(options.output_dir)
                result.collisions.append(f"{target_relative} -> {preserved_relative}")
                logger.warning(
                    "目标同名，使用保留路径：%s -> %s",
                    source,
                    collision_target,
                )
                target = collision_target

            modified = _copy_with_replacements(
                source,
                target,
                mapping,
                replace_text=options.replace_text_references,
            )
            result.copied_files += 1
            if target_relative != relative:
                result.renamed_files += 1
            if modified:
                result.modified_text_files += 1
            notify(f"复制文件 {index}/{len(files)}：{relative}")

        logger.info(
            "完成：复制 %d，改名 %d，内容更新 %d，未解析 UUID %d，冲突 %d",
            result.copied_files,
            result.renamed_files,
            result.modified_text_files,
            len(result.unresolved),
            len(result.collisions),
        )
        return result
    except OSError as exc:
        logger.exception("文件处理失败")
        raise ConversionError(f"文件处理失败：{exc}") from exc
    finally:
        handler.close()
        logger.removeHandler(handler)


def _validate_paths(input_dir: Path, output_dir: Path) -> None:
    input_resolved = input_dir.expanduser().resolve()
    output_resolved = output_dir.expanduser().resolve()
    if not input_resolved.is_dir():
        raise ConversionError(f"输入文件夹不存在：{input_dir}")
    if input_resolved == output_resolved:
        raise ConversionError("输出文件夹不能与输入文件夹相同")
    if input_resolved in output_resolved.parents:
        raise ConversionError("输出文件夹不能位于输入文件夹内部")


def _iter_files(root: Path, *, recursive: bool) -> Iterable[Path]:
    iterator = root.rglob("*") if recursive else root.glob("*")
    return (path for path in iterator if path.is_file())


def _collect_candidates(files: Iterable[Path], *, replace_text: bool) -> set[str]:
    candidates: set[str] = set()
    for path in files:
        candidates.update(find_uuids(path.name))
        if replace_text and path.suffix.lower() in TEXT_SUFFIXES:
            try:
                candidates.update(find_uuids(path.read_text(encoding="utf-8-sig")))
            except (OSError, UnicodeDecodeError):
                continue
    return candidates


def _replace_path_uuids(path: Path, mapping: dict[str, str]) -> Path:
    parts: list[str] = []
    for part in path.parts:
        updated = part
        for source_uuid, target_uuid in mapping.items():
            updated = updated.replace(source_uuid, target_uuid)
        parts.append(updated)
    return Path(*parts)


def _copy_with_replacements(
    source: Path,
    target: Path,
    mapping: dict[str, str],
    *,
    replace_text: bool,
) -> bool:
    if replace_text and source.suffix.lower() in TEXT_SUFFIXES:
        try:
            content = source.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            shutil.copy2(source, target)
            return False
        updated = content
        for source_uuid, target_uuid in mapping.items():
            updated = updated.replace(source_uuid, target_uuid)
        if updated != content:
            target.write_text(updated, encoding="utf-8", newline="")
            shutil.copystat(source, target)
            return True
    shutil.copy2(source, target)
    return False


def _unique_collision_path(target: Path) -> Path:
    counter = 1
    while True:
        candidate = target.with_name(
            f"{target.stem}.uuid-conflict-{counter}{target.suffix}"
        )
        if not candidate.exists():
            return candidate
        counter += 1


def _create_run_logger(logs_dir: Path) -> tuple[logging.Logger, logging.Handler, Path]:
    logs_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    log_file = logs_dir / f"conversion-{stamp}.log"
    logger = logging.getLogger(f"minecraft_uuid_convert.run.{stamp}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s")
    )
    logger.addHandler(handler)
    return logger, handler, log_file
