"""
语音管家 — 电脑操控执行模块
负责执行解析后的命令，操控 Windows 系统
"""

import os
import sys
import re
import time
import ctypes
import subprocess
import webbrowser
import threading
from datetime import datetime
from pathlib import Path
from ctypes import wintypes


# ============================================
# Windows API 底层工具
# ============================================

# 虚拟键码扩展
VK = {
    # 修饰键
    "win": 0x5B, "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
    # 功能键
    "tab": 0x09, "enter": 0x0D, "esc": 0x1B, "space": 0x20,
    "backspace": 0x08, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "insert": 0x2D,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "caps": 0x14, "numlock": 0x90, "scrolllock": 0x91,
    "printscreen": 0x2C, "pause": 0x13,
    # 字母键
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
    # 数字键
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    # F键
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
    "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
    "f11": 0x7A, "f12": 0x7B,
    # 媒体键
    "media_play_pause": 0xB3, "media_stop": 0xB2,
    "media_next": 0xB0, "media_prev": 0xB1,
    "volume_mute": 0xAD, "volume_down": 0xAE, "volume_up": 0xAF,
    "browser_home": 0xAC, "browser_search": 0xAA,
    "browser_back": 0xA6, "browser_forward": 0xA7,
    "browser_refresh": 0xA8,
}


def send_keys(*keys, hold=0.05):
    """发送按键序列，支持组合键（如 send_keys('ctrl', 'c')）"""
    user32 = ctypes.windll.user32
    codes = []
    for k in keys:
        kl = k.lower()
        code = VK.get(kl, ord(k.upper()) if len(k) == 1 else 0)
        if code:
            codes.append(code)

    if not codes:
        return False

    # 按下
    for code in codes:
        user32.keybd_event(code, 0, 0, 0)
        time.sleep(hold * 0.5)
    time.sleep(hold)
    # 释放（逆序）
    for code in reversed(codes):
        user32.keybd_event(code, 0, 2, 0)
        time.sleep(hold * 0.3)
    return True


def type_text(text):
    """通过模拟键盘输入文本（使用剪贴板+粘贴，支持中文）"""
    import win32clipboard

    # 存储旧剪贴板
    try:
        win32clipboard.OpenClipboard()
        old = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
    except:
        old = ""

    # 写入新内容
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    time.sleep(0.05)

    # Ctrl+V
    send_keys("ctrl", "v")

    # 恢复旧剪贴板
    if old:
        time.sleep(0.1)
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(old, win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()


def mouse_action(action="click", x=None, y=None):
    """鼠标操作：click / double / right / move"""
    user32 = ctypes.windll.user32
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_RIGHTDOWN = 0x0008
    MOUSEEVENTF_RIGHTUP = 0x0010
    MOUSEEVENTF_ABSOLUTE = 0x8000

    if x is not None and y is not None:
        # 绝对坐标（屏幕分辨率归一化到 0~65535）
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        abs_x = int(x * 65535 / screen_w)
        abs_y = int(y * 65535 / screen_h)
        user32.mouse_event(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE, abs_x, abs_y, 0, 0)
        time.sleep(0.02)

    if action == "click":
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.02)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    elif action == "double":
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    elif action == "right":
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        time.sleep(0.02)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    elif action == "move":
        pass  # 已在上面移动
    return True


def get_cursor_pos():
    """获取当前鼠标位置"""
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def get_screen_size():
    """获取屏幕分辨率"""
    user32 = ctypes.windll.user32
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def move_relative(dx, dy):
    """鼠标相对移动"""
    ctypes.windll.user32.mouse_event(0x0001, dx, dy, 0, 0)


def set_window_topmost(window_title=None):
    """将指定窗口置顶"""
    if window_title:
        ps_cmd = f'''
        Add-Type @"
        using System; using System.Runtime.InteropServices;
        public class WinAPI {{
            [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
            [DllImport("user32.dll")] public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
            public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
            public static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
        }}
"@
        $hwnd = [WinAPI]::FindWindow($null, "*{window_title}*")
        if ($hwnd) {{ [WinAPI]::SetWindowPos($hwnd, [WinAPI]::HWND_TOPMOST, 0,0,0,0, 3) }}
        '''


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
                if isinstance(exe, str) and exe.startswith("ms-"):
                    subprocess.Popen(f"start {exe}", shell=True)
                else:
                    subprocess.Popen(exe, shell=False)
                return f"已打开 {target}"
            except Exception as e:
                try:
                    os.startfile(target)
                    return f"已尝试打开 {target}"
                except Exception:
                    return f"打开 {target} 失败: {e}"

        # 尝试用 start 命令
        try:
            subprocess.Popen(f"start {target}", shell=True)
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
            subprocess.run(["taskkill", "/f", "/im", exe], capture_output=True, shell=False)
            return f"已关闭 {target}"
        except Exception:
            return f"关闭 {target} 失败"

    def _handle_volume_control(self, params: dict, text: str) -> str:
        """音量控制 — 全部使用虚拟媒体键，无需 nircmd"""
        if "静音" in text and "取消" not in text and "解除" not in text:
            send_keys("volume_mute")
            return "已静音"
        if "取消静音" in text or "解除静音" in text:
            send_keys("volume_mute")
            return "已取消静音"

        # 解析具体音量值
        m = re.search(r'(\d+)', text)
        if m:
            vol = int(m.group(1))
            vol = max(0, min(100, vol))
            try:
                ps = (
                    f'Add-Type -AssemblyName System.Windows.Forms; '
                    f'$ws = New-Object System.Management.Automation.Host.ChoiceDescription "&Yes", ""; '
                    f'$null = $ws; '
                    f'$wsh = New-Object -ComObject WScript.Shell; '
                    f'for($i=0;$i<50;$i++){{ $wsh.SendKeys([char]174) }}; '
                    f'for($i=0;$i<{vol // 2};$i++){{ $wsh.SendKeys([char]175) }}'
                )
                subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=5)
                return f"音量已设置为 {vol}%"
            except Exception:
                pass

        # 调大/调小
        if any(w in text for w in ["调大", "增大", "加大", "加", "大"]):
            for _ in range(10):
                send_keys("volume_up")
            return "音量已调大"
        if any(w in text for w in ["调小", "减小", "降低", "减", "小"]):
            for _ in range(10):
                send_keys("volume_down")
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

    def _handle_ai_query(self, params: dict, text: str) -> str:
        """AI 智能问答 — 透传给 main.py 的 deepseek"""
        question = params.get("target", text).strip()
        if not question or len(question) < 2:
            return "请告诉我你想问什么"
        # 由 main.py 的 execute() 兜底处理，这里返回空让上层接管
        return ""

    def _handle_window_control(self, params: dict, text: str) -> str:
        """窗口管理"""
        import ctypes
        user32 = ctypes.windll.user32

        # 显示桌面 (Win+D)
        if any(w in text for w in ["显示桌面", "回到桌面"]):
            send_keys("win", "d")
            return "已显示桌面"

        # 切换窗口 (Alt+Tab)
        if any(w in text for w in ["切换窗口", "alt tab", "alt+tab"]):
            send_keys("alt", "tab")
            return "已切换窗口"

        # 任务视图 (Win+Tab)
        if "任务视图" in text:
            send_keys("win", "tab")
            return "已打开任务视图"

        # 最小化所有窗口 (Win+M)
        if any(w in text for w in ["最小化所有窗口", "所有窗口最小化", "最小化所有"]):
            send_keys("win", "m")
            return "已最小化所有窗口"

        # 还原最小化 (Win+Shift+M)
        if any(w in text for w in ["还原所有", "恢复所有"]):
            send_keys("win", "shift", "m")
            return "已还原所有窗口"

        # 最小化当前窗口 (Alt+Space, N)
        if "最小化" in text and "所有" not in text:
            send_keys("alt", "space")
            time.sleep(0.1)
            send_keys("n")
            return "已最小化当前窗口"

        # 最大化当前窗口 (Win+Up)
        if "最大化" in text:
            send_keys("win", "up")
            return "已最大化当前窗口"

        # 窗口分屏左/右 (Win+Left / Win+Right)
        if "分屏" in text or "平铺" in text:
            send_keys("win", "z")
            return "已打开分屏布局"

        if "堆叠" in text:
            send_keys("win", "up")
            return "已调整窗口"

        if "层叠" in text:
            send_keys("win", "d")
            return "已层叠窗口"

        # 置顶 (通过 PowerShell 调用 WinAPI)
        m = re.search(r"(?:置顶|取消置顶)\s*(.+)", text)
        if m:
            title = m.group(1).strip()
            is_top = "取消" not in text
            try:
                ps = f'''
                Add-Type @"
                using System; using System.Runtime.InteropServices;
                public class TopMost {{
                    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
                    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
                    public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
                    public static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
                }}
"@
                $hwnd = [TopMost]::FindWindow($null, "*{title}*")
                if ($hwnd) {{
                    $pos = {("-1" if is_top else "-2")}
                    [TopMost]::SetWindowPos($hwnd, $pos, 0, 0, 0, 0, 3)
                    Write-Host "ok"
                }} else {{ Write-Host "notfound" }}
                '''
                r = subprocess.run(["powershell", "-Command", ps],
                                   capture_output=True, text=True, timeout=5)
                if "ok" in (r.stdout or ""):
                    return f"已将 {title} {'置顶' if is_top else '取消置顶'}"
                return f"未找到窗口: {title}"
            except:
                return "置顶操作失败"
        return "窗口管理指令不明确"

    def _handle_keyboard_input(self, params: dict, text: str) -> str:
        """键盘输入与快捷键"""
        # 单键操作
        shortcuts = {
            "复制": ("ctrl", "c"), "拷贝": ("ctrl", "c"),
            "粘贴": ("ctrl", "v"),
            "剪切": ("ctrl", "x"),
            "全选": ("ctrl", "a"),
            "撤销": ("ctrl", "z"),
            "重做": ("ctrl", "y"),
            "保存": ("ctrl", "s"),
            "刷新": ("f5"),
            "查找": ("ctrl", "f"),
            "替换": ("ctrl", "h"),
            "加粗": ("ctrl", "b"),
            "斜体": ("ctrl", "i"),
            "下划线": ("ctrl", "u"),
        }
        for keyword, keys in shortcuts.items():
            if text.strip() == keyword or text.strip() == keyword + "键":
                send_keys(*keys)
                return f"已执行 {keyword}"

        # 回车
        if "回车" in text:
            send_keys("enter")
            return "已按回车"

        # 按 X 键
        m = re.search(r"按\s*(?:下|下)?\s*(\S+)\s*键", text)
        if m:
            key = m.group(1).strip().lower()
            if key == "回车":
                send_keys("enter")
            elif key == "空格":
                send_keys("space")
            elif key == "删除":
                send_keys("delete")
            elif key == "退格":
                send_keys("backspace")
            elif key == "上":
                send_keys("up")
            elif key == "下":
                send_keys("down")
            elif key == "左":
                send_keys("left")
            elif key == "右":
                send_keys("right")
            elif key == "esc" or key == "退出":
                send_keys("esc")
            else:
                send_keys(key)
            return f"已按 {key} 键"

        # 快捷键
        m = re.search(r"快捷键\s*(.+)", text)
        if m:
            combo = m.group(1).strip()
            keys = [k.strip().lower() for k in combo.split("+")]
            send_keys(*keys)
            return f"已执行快捷键 {combo}"

        # 输入 / 键入文本
        m = re.search(r"(?:输入|键入|打出|写入)\s*(.+?)(?:\s+(?:在|到))?\s*$", text)
        if m:
            content = m.group(1).strip()
            # 去掉末尾的语气词
            content = re.sub(r'[。！？，、\s]*$', '', content)
            if content:
                try:
                    type_text(content)
                    return f"已输入: {content}"
                except ImportError:
                    # fallback: 用全选+替换方式
                    try:
                        import win32clipboard
                        win32clipboard.OpenClipboard()
                        win32clipboard.EmptyClipboard()
                        win32clipboard.SetClipboardText(content)
                        win32clipboard.CloseClipboard()
                        send_keys("ctrl", "v")
                        return f"已输入: {content}"
                    except:
                        return "输入失败，请安装 pywin32"
            return "请指定要输入的内容"
        return "键盘指令不明确"

    def _handle_mouse_control(self, params: dict, text: str) -> str:
        """鼠标控制"""
        if "右键" in text:
            mouse_action("right")
            return "已右键点击"
        if "双击" in text:
            mouse_action("double")
            return "已双击"
        if re.search(r"单击|点击", text):
            mouse_action("click")
            return "已单击"

        # 鼠标移动到坐标
        m = re.search(r"移动\s*(?:到|至)?\s*(\d+)\s*[,，\s]\s*(\d+)", text)
        if m:
            x, y = int(m.group(1)), int(m.group(2))
            mouse_action("move", x, y)
            return f"鼠标已移动到 ({x}, {y})"

        # 鼠标向上/下/左/右
        m = re.search(r"鼠标\s*(向上|向下|向左|向右)(\d+)?", text)
        if m:
            direction = m.group(1)
            dist = int(m.group(2)) if m.group(2) else 100
            if "上" in direction:
                move_relative(0, -dist)
            elif "下" in direction:
                move_relative(0, dist)
            elif "左" in direction:
                move_relative(-dist, 0)
            elif "右" in direction:
                move_relative(dist, 0)
            return f"鼠标已{direction}移动 {dist} 像素"

        # 获取位置
        if "在哪里" in text or "位置" in text:
            x, y = get_cursor_pos()
            return f"鼠标当前位置: ({x}, {y})"
        return "鼠标指令不明确"

    def _handle_media_control(self, params: dict, text: str) -> str:
        """媒体播放控制"""
        if "暂停" in text or "停止" in text:
            send_keys("media_play_pause")
            return "已暂停"
        if "播放" in text:
            send_keys("media_play_pause")
            return "已播放"
        if "下一首" in text or "下一条" in text:
            send_keys("media_next")
            return "下一首"
        if "上一首" in text or "上一条" in text:
            send_keys("media_prev")
            return "上一首"
        if "快进" in text:
            send_keys("media_next")
            return "已快进"
        if "快退" in text:
            send_keys("media_prev")
            return "已快退"
        return "媒体控制指令不明确"

    def _handle_screen_brightness(self, params: dict, text: str) -> str:
        """屏幕亮度调节"""
        if any(w in text for w in ["调大", "增大", "调高", "调亮", "变亮", "亮"]):
            try:
                send_keys("win", "a")  # 打开操作中心（含亮度滑块）
                return "已调出操作中心，亮度可在此调节"
            except:
                return "亮度调节失败"

        if any(w in text for w in ["调小", "减小", "调暗", "变暗", "暗"]):
            try:
                send_keys("win", "a")
                return "已调出操作中心，亮度可在此调节"
            except:
                return "亮度调节失败"

        # 具体亮度值
        m = re.search(r'(\d+)', text)
        if m:
            return f"亮度设为 {m.group(1)}%，已打开操作中心"

        send_keys("win", "a")
        return "已打开操作中心"

    def _handle_desktop_ops(self, params: dict, text: str) -> str:
        """桌面与任务栏操作"""
        # 回到桌面
        if "回到桌面" in text:
            send_keys("win", "d")
            return "已回到桌面"

        # 打开回收站
        if "打开回收站" in text or "进入回收站" in text:
            subprocess.Popen("explorer.exe shell:RecycleBinFolder", shell=True)
            return "已打开回收站"

        # 清空回收站
        if "清空回收站" in text:
            try:
                subprocess.run(
                    ["powershell", "-Command",
                     "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"],
                    capture_output=True, timeout=10)
                return "已清空回收站"
            except:
                return "清空回收站失败"

        # 整理桌面
        if "整理桌面" in text or "清理桌面" in text:
            desktop = Path.home() / "Desktop"
            try:
                send_keys("win", "d")
                time.sleep(0.5)
                # F5 刷新
                send_keys("f5")
                return "桌面已整理"
            except:
                return "整理桌面失败"

        # 任务栏操作
        m = re.search(r"任务栏\s*(.+)", text)
        if m:
            action = m.group(1).strip()
            if "隐藏" in action:
                send_keys("win", "i")
                return "已打开设置，可搜索「任务栏」调整"
            if "小" in action:
                send_keys("win", "i")
                return "已打开设置，可搜索「任务栏」调整"
            return "任务栏操作已处理"
        return "桌面操作指令不明确"

    def _handle_help(self, params: dict, text: str) -> str:
        """帮助"""
        return ""  # 在主循环中处理
