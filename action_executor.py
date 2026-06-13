"""
语音管家 — 电脑操控执行模块
负责执行解析后的命令，操控 Windows 系统
"""

import os
import sys
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path


class ActionExecutor:
    """命令执行器 — 操控电脑"""

    # 常见应用名 → 可执行文件映射
    APP_MAP = {
        "记事本": "notepad.exe",
        "notepad": "notepad.exe",
        "计算器": "calc.exe",
        "calculator": "calc.exe",
        "画图": "mspaint.exe",
        "paint": "mspaint.exe",
        "浏览器": "msedge.exe",
        "edge": "msedge.exe",
        "chrome": "chrome.exe",
        "谷歌": "chrome.exe",
        "资源管理器": "explorer.exe",
        "explorer": "explorer.exe",
        "cmd": "cmd.exe",
        "终端": "cmd.exe",
        "terminal": "wt.exe",
        "powershell": "powershell.exe",
        "任务管理器": "taskmgr.exe",
        "task manager": "taskmgr.exe",
        "word": "winword.exe",
        "excel": "excel.exe",
        "ppt": "powerpnt.exe",
        "微信": "wechat.exe",
        "wechat": "wechat.exe",
        "qq": "qq.exe",
        "vs code": "code.exe",
        "vscode": "code.exe",
        "设置": "ms-settings:",
        "settings": "ms-settings:",
        "截图工具": "snippingtool.exe",
    }

    def execute(self, cmd_name: str, params: dict, asr_text: str = "") -> str:
        """执行命令并返回结果"""
        handler = getattr(self, f"_handle_{cmd_name}", None)
        if handler:
            return handler(params, asr_text)
        return f"未找到命令处理器: {cmd_name}"

    def _handle_open_app(self, params: dict, text: str) -> str:
        """打开应用"""
        target = params.get("target", "").strip()
        if not target:
            return "请指定要打开的应用名称"

        # 先在映射表中查找
        exe = self.APP_MAP.get(target)
        if exe:
            try:
                if exe.startswith("ms-"):
                    subprocess.Popen(["start", exe], shell=True)
                else:
                    subprocess.Popen([exe], shell=True)
                return f"已打开 {target}"
            except Exception as e:
                return f"打开 {target} 失败: {e}"

        # 尝试用 start 命令
        try:
            subprocess.Popen(["start", target], shell=True)
            return f"已尝试打开 {target}"
        except Exception:
            return f"未找到应用: {target}"

    def _handle_close_app(self, params: dict, text: str) -> str:
        """关闭应用"""
        target = params.get("target", "").strip()
        if not target:
            return "请指定要关闭的应用名称"

        exe = self.APP_MAP.get(target, target)
        try:
            subprocess.run(["taskkill", "/f", "/im", exe],
                           capture_output=True, shell=True)
            return f"已关闭 {target}"
        except Exception:
            return f"关闭 {target} 失败"

    def _handle_volume_control(self, params: dict, text: str) -> str:
        """音量控制"""
        import subprocess
        if "静音" in text:
            subprocess.run(["nircmd", "mutesysvolume", "1"], shell=True)
            return "已静音"
        if "取消静音" in text or "解除静音" in text:
            subprocess.run(["nircmd", "mutesysvolume", "0"], shell=True)
            return "已取消静音"

        # 解析音量值
        import re
        vol_match = re.search(r'(\d+)', text)
        if vol_match:
            vol = int(vol_match.group(1))
            vol = max(0, min(100, vol))
            try:
                # 使用 PowerShell 设置音量
                ps_cmd = f'''
                Add-Type -TypeDefinition @'
                using System.Runtime.InteropServices;
                [Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
                interface IAudioEndpointVolume {{
                    int GetMasterVolumeLevelScalar(out float fLevel);
                    int SetMasterVolumeLevelScalar(float fLevel, System.Guid pguidEventContext);
                }}
'@
                $null
                '''
                subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
            except Exception:
                pass

            # 更简单的方式：用 nircmd 或发送按键
            try:
                subprocess.run(["nircmd", "setsysvolume", str(int(vol * 655.35))], shell=True)
                return f"音量已设置为 {vol}%"
            except Exception:
                pass

        if "调大" in text or "增大" in text or "加大" in text:
            for _ in range(5):
                subprocess.run(["nircmd", "changesysvolume", "2000"], shell=True)
            return "音量已调大"
        if "调小" in text or "减小" in text or "降低" in text:
            for _ in range(5):
                subprocess.run(["nircmd", "changesysvolume", "-2000"], shell=True)
            return "音量已调小"

        return "音量控制指令不明确"

    def _handle_system_control(self, params: dict, text: str) -> str:
        """系统控制"""
        if "关机" in text:
            subprocess.run(["shutdown", "/s", "/t", "30"], shell=True)
            return "电脑将在 30 秒后关机"
        if "重启" in text:
            subprocess.run(["shutdown", "/r", "/t", "10"], shell=True)
            return "电脑将在 10 秒后重启"
        if "锁屏" in text:
            subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], shell=True)
            return "已锁屏"
        if "休眠" in text:
            subprocess.run(["shutdown", "/h"], shell=True)
            return "电脑将进入休眠"
        if "注销" in text:
            subprocess.run(["shutdown", "/l"], shell=True)
            return "正在注销"
        return "系统控制指令不明确"

    def _handle_web_search(self, params: dict, text: str) -> str:
        """联网搜索"""
        target = params.get("target", "").strip()
        if not target:
            return "请指定搜索内容"
        url = f"https://www.baidu.com/s?wd={target}"
        webbrowser.open(url)
        return f"已打开浏览器搜索: {target}"

    def _handle_file_operation(self, params: dict, text: str) -> str:
        """文件操作"""
        target = params.get("target", "").strip()
        if "打开文件" in text or "打开" in text:
            path = Path(target)
            if path.exists():
                os.startfile(str(path))
                return f"已打开文件: {target}"
            return f"文件不存在: {target}"
        if "新建文件夹" in text or "创建文件夹" in text:
            path = Path(target)
            path.mkdir(parents=True, exist_ok=True)
            return f"已创建文件夹: {target}"
        if "新建文件" in text or "创建文件" in text:
            path = Path(target)
            path.touch()
            return f"已创建文件: {target}"
        return "文件操作指令不明确"

    def _handle_time_query(self, params: dict, text: str) -> str:
        """时间查询"""
        now = datetime.now()
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        if "星期" in text or "周" in text:
            return f"今天是{weekdays[now.weekday()]}"
        if "日期" in text:
            return f"今天是 {now.year}年{now.month}月{now.day}日"
        return f"现在是 {now.hour}点{now.minute}分{now.second}秒"

    def _handle_weather_query(self, params: dict, text: str) -> str:
        """天气查询"""
        target = params.get("target", "").strip()
        city = target or "北京"
        url = f"https://www.baidu.com/s?wd={city}+天气"
        webbrowser.open(url)
        return f"已打开浏览器查询 {city} 天气"

    def _handle_screenshot(self, params: dict, text: str) -> str:
        """截图"""
        try:
            subprocess.Popen(["snippingtool.exe"], shell=True)
            return "已打开截图工具"
        except Exception:
            # Win+Shift+S
            import ctypes
            ctypes.windll.user32.keybd_event(0x5B, 0, 0, 0)  # Win
            ctypes.windll.user32.keybd_event(0x10, 0, 0, 0)  # Shift
            ctypes.windll.user32.keybd_event(0x53, 0, 0, 0)  # S
            ctypes.windll.user32.keybd_event(0x53, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x10, 0, 2, 0)
            ctypes.windll.user32.keybd_event(0x5B, 0, 2, 0)
            return "已触发截图快捷键"

    def _handle_help(self, params: dict, text: str) -> str:
        """帮助"""
        return ""  # 在主循环中处理
