# ✨ MCUUID转换器 / MinecraftUUIDConvert  
通过解析usernamecache.json转换数据文件，支持几乎所有以UUID命名的数据文件！  
Convert uuid through parsing usernamecache.json &amp; copying files.  

##  ❤️ 要求 / Requirements  
Python 3.12.x  

## 🌍 环境 / Environments  
开发环境：Windows 11 24H2 26100.1949 
Developing environment: Windows 11 24H2 26100.1949  
It theoretically supports for all the modern Microsoft Windows Operating System.But I haven't tested it, please try it specifically!  
It haven't been tested on any linux system.If you have a need, you can test or modify it yourself.  

## 🤞 使用方式 / Usage  
1. 下载Python3.12并安装（勾选添加到path）  
2. 下载本工具（通过main分支或release均可）  
3. 放入任何你想要转换的数据（例如world/playerdata，world/ftbquests等）
4. 复制前后的usernamecache.json到usernamecache1.json与usernamecache2.json
  (tip: 如果你的usernamecache未重置过，可以将该usernamecache复制为两份，软件将会自动识别前后usernamecache，默认第一个出现的UUID为待转换，最后一个出现的为需要转换成的UUID)
5. 双击运行main.py
6. 查看导出文件(output/)
   (tip: deleted/:归档的文件（存档中新生成的数据文件，默认删除，可按需保存回），unconverted/:未转换的文件，未找到UUID，无法转换)  
**注意：在转换前请确保所有玩家均已重进一次生成新的UUID**  
![Image](https://youke1.picui.cn/s1/2025/08/15/689eeec30701f.png)
