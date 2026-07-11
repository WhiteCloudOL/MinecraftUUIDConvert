"""Headless command-line interface for UUID migration."""

from __future__ import annotations

import argparse
from pathlib import Path

from minecraft_uuid_convert.cache import load_player_cache
from minecraft_uuid_convert.converter import (
    ConversionMode,
    ConversionOptions,
    convert_directory,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="minecraft-uuid-convert",
        description="递归镜像 Minecraft 世界或数据目录并转换玩家 UUID。",
    )
    parser.add_argument("input", nargs="?", default="input", help="世界或数据目录")
    parser.add_argument("-o", "--output", default="output", help="输出目录")
    parser.add_argument(
        "-m",
        "--mode",
        choices=[mode.value for mode in ConversionMode],
        default=ConversionMode.ONLINE_TO_OFFLINE.value,
        help="转换方向",
    )
    parser.add_argument("-c", "--cache", type=Path, help="可选玩家缓存 JSON")
    parser.add_argument("--logs", type=Path, default=Path("logs"), help="日志目录")
    parser.add_argument("--no-network", action="store_true", help="禁用在线玩家查询")
    parser.add_argument("--no-text", action="store_true", help="只转换路径和文件名")
    parser.add_argument("--no-recursive", action="store_true", help="只处理目录第一层")
    return parser


def run_cli(arguments: list[str] | None = None) -> int:
    """Run a conversion from command-line arguments."""
    args = build_parser().parse_args(arguments)
    cache = load_player_cache(args.cache) if args.cache else None
    result = convert_directory(
        ConversionOptions(
            input_dir=Path(args.input),
            output_dir=Path(args.output),
            logs_dir=args.logs,
            mode=ConversionMode(args.mode),
            cache=cache,
            use_network=not args.no_network,
            replace_text_references=not args.no_text,
            recursive=not args.no_recursive,
        ),
        progress=print,
    )
    print(
        "转换完成："
        f"复制 {result.copied_files}/{result.total_files} 个文件，"
        f"改名 {result.renamed_files} 个，"
        f"更新文本 {result.modified_text_files} 个，"
        f"未解析 UUID {len(result.unresolved)} 个。"
    )
    if result.log_file:
        print(f"日志：{result.log_file}")
    return 0 if not result.collisions else 2
