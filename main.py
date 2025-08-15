"""
AppName: Minecraft UUID Convert
Author: WhiteCloudCN
Update Time: 2025/08/15 14:50
Version: 0.1
"""
from datetime import datetime
import json
import shutil
from pathlib import Path
from typing import Dict, Set


def log_to_both(file, message):
    """同时输出到文件和控制台"""
    print(message)
    file.write(message + "\n")


def ParseUUID(file_path: str, keep_first: bool = True) -> Dict[str, str]:
    Path("./logs").mkdir(exist_ok=True)
    with open(file_path, 'r', encoding='utf-8') as file:
        original_data = json.load(file)

    name_to_uuids = {}
    for uuid, name in original_data.items():
        if name not in name_to_uuids:
            name_to_uuids[name] = []
        name_to_uuids[name].append(uuid)

    duplicates = {name: uuids for name, uuids in name_to_uuids.items() if len(uuids) > 1}
    if duplicates:
        with open("logs/users.log", "a", encoding="utf-8") as user_log:
            header = f"\n⚠️ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 发现重复用户名:"
            log_to_both(user_log, header)
            for name, uuids in duplicates.items():
                msg = f"  用户名 '{name}' 对应 {len(uuids)} 个UUID:"
                log_to_both(user_log, msg)
                for i, uuid in enumerate(uuids, 1):
                    msg = f"    {i}. {uuid}"
                    log_to_both(user_log, msg)
            choice = "\n将保留每个用户名对应的" + ("第一个" if keep_first else "最后一个") + "UUID"
            log_to_both(user_log, choice)

    result = {}
    for uuid, name in original_data.items():
        if name not in result:
            result[name] = uuid
        elif not keep_first:
            result[name] = uuid

    return result


def ConvertUUID(firstDict: Dict[str, str], secondDict: Dict[str, str],
               input_dir='./input',
               output_dir='./output',
               deleted_dir='./deleted',
               unconverted_dir='./unconverted') -> None:
    Path("./logs").mkdir(exist_ok=True)
    Path(output_dir).mkdir(exist_ok=True)
    Path(deleted_dir).mkdir(exist_ok=True)
    Path(unconverted_dir).mkdir(exist_ok=True)

    # 清空输出文件夹
    for folder in [output_dir, deleted_dir, unconverted_dir]:
        for item in Path(folder).glob('*'):
            item.unlink() if item.is_file() else shutil.rmtree(item)
        readme_path = Path(folder) / "README.txt"
        with open(readme_path, 'w', encoding='utf-8') as f:
            if folder == output_dir:
                content = [
                    "此目录包含转换后的文件（已更新为新UUID）",
                    "由 Minecraft UUID Convert 生成，BY WhiteCloudCN / 清蒸云鸭",
                    "生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ]
            elif folder == deleted_dir:
                content = [
                    "此目录包含原始新UUID文件的备份",
                    "由 Minecraft UUID Convert 生成，BY WhiteCloudCN / 清蒸云鸭",
                    "生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ]
            else:
                content = [
                    "此目录包含未被转换的原始文件",
                    "可能原因：",
                    "- 文件名不匹配任何已知UUID",
                    "- 缺少对应的用户名映射",
                    "由 Minecraft UUID Convert 生成，BY WhiteCloudCN / 清蒸云鸭",
                    "生成时间: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ]
            f.write("\n".join(content))

    uuid_mapping = {}
    for username, old_uuid in firstDict.items():
        if username in secondDict:
            uuid_mapping[old_uuid] = secondDict[username]

    input_files = list(Path(input_dir).glob('*'))
    processed_files: Set[Path] = set()
    count_file = [0, 0, 0]
    archived_players = set()

    with open("logs/converted.log", "a", encoding="utf-8") as conv_log, \
         open("logs/deleted.log", "a", encoding="utf-8") as del_log, \
         open("logs/unconverted.log", "a", encoding="utf-8") as unconv_log:

        timestamp = f"\n===== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ====="
        for log_file in [conv_log, del_log, unconv_log]:
            log_file.write(timestamp + "\n")
        print(timestamp)

        for input_file in input_files:
            if not input_file.is_file():
                continue
            stem = input_file.stem
            if stem in uuid_mapping:
                new_uuid = uuid_mapping[stem]
                new_name = input_file.name.replace(stem, new_uuid)
                shutil.copy2(input_file, Path(output_dir) / new_name)
                processed_files.add(input_file)
                count_file[0] += 1
                msg = f"🔄 已转换: {input_file} -> {output_dir}/{new_name}"
                log_to_both(conv_log, msg)
            elif stem in secondDict.values():
                shutil.copy2(input_file, Path(deleted_dir) / input_file.name)
                processed_files.add(input_file)
                count_file[1] += 1
                msg = f"✅ 已归档: {input_file} -> {deleted_dir}/{input_file.name}"
                log_to_both(del_log, msg)
                # 记录已归档的玩家名
                for username, uuid in secondDict.items():
                    if uuid == stem:
                        archived_players.add(username)
                        player_msg = f"   玩家名: {username}"
                        log_to_both(del_log, player_msg)
                        break
                log_to_both(del_log, " ")
        # 输出已归档玩家汇总
        if archived_players:
            log_to_both(del_log, "\n已归档玩家汇总:")
            for player in sorted(archived_players):
                log_to_both(del_log, f"- {player}")
            log_to_both(del_log, "")

        for input_file in input_files:
            if input_file.is_file() and input_file not in processed_files:
                shutil.copy2(input_file, Path(unconverted_dir) / input_file.name)
                count_file[2] += 1
                msg = f"⚠️ 未转换: {input_file} -> {unconverted_dir}/{input_file.name}\n"
                log_to_both(unconv_log, msg)

        summary = (f"\n🔄 已转换{count_file[0]}个文件\n"
                   f"✅ 重复UUID文件 {count_file[1]} 个，已归档\n"
                   f"⚠️ 未查询到UUID {count_file[2]} 个，未转换\n")
        print(summary)
        for log_file in [conv_log, del_log, unconv_log]:
            log_file.write(summary)


if __name__ == '__main__':
    Path("./input").mkdir(exist_ok=True)
    print("Minecraft UUID Convert v0.1\n"
          " By WhiteCloudCN\n"
          "✨ 功能：\n"
          "转换存档玩家文件，支持任意以uuid命名的数据文件\n"
          "要求有前后usernamecache（玩家必须进入一次）文件"
          "在大量数据下很方便！！！\n"
          "\n"
          "✨ 用法：\n"
          "1.将待转换的playerdata文件放置于 input/ 文件夹内\n"
          "2.将旧 usernamecache.json 重命名为 usernamecache1.json 放置于根目录\n"
          "3.将新 usernamecache.json 重命名为 usernamecache2.json 放置于根目录\n"
          "Tip: \n"
          "如果你前后并没有重置 usernamecache.json ,那么直接将 usernamecache.json 复制成两份或许也是可行的！\n"
          "不过最好建议自行筛选一下 usernamecache.json 避免干扰\n")
    choice = input("输入 Y/y 执行转换:")
    if choice.upper() == "Y":
        try:
            message = "😠 解析待转换的usernamecache1.json中..."
            log_to_both(open("logs/users.log", 'a', encoding='utf-8'), message)
            firstDict = ParseUUID("usernamecache1.json", keep_first=True)
            message = "😠 usernamecache1.json解析完成！\n"
            log_to_both(open("logs/users.log", 'a', encoding='utf-8'), message)
            message = "😠 解析待转换的usernamecache2.json中..."
            log_to_both(open("logs/users.log", 'a', encoding='utf-8'), message)
            secondDict = ParseUUID("usernamecache2.json", keep_first=False)
            message = "😠 usernamecache2.json解析完成！\n"
            log_to_both(open("logs/users.log", 'a', encoding='utf-8'), message)

            start_msg = "=== 转换开始 ==="
            print(start_msg)
            ConvertUUID(firstDict, secondDict)
            end_msg = "=== 转换完成 ==="
            print(end_msg)
            input("按下任意键关闭...")
            exit()
        except FileNotFoundError as e:
            error_msg = (f"❌ 错误: {e}\n"
                        "请确保准备好以下文件:\n"
                        "1. usernamecache1.json - 包含旧UUID映射\n"
                        "2. usernamecache2.json - 包含新UUID映射\n"
                        "3. input/ - 包含需要转换的文件")
            print(error_msg)
            input("按下任意键关闭...")
            exit()
    else:
        input("按下任意键关闭...")
        exit()