"""
语音管家 v3.0 — 多轮对话 + 完整电脑操控
唤醒词 → 进入对话模式 → 连续发指令 → 说"退出"回到监听
"""

import sys, os, json, time, queue, threading, subprocess, webbrowser, re
import urllib.request, urllib.error
from datetime import datetime
from pathlib import Path

# ============================================
# 配置
# ============================================
WAKE_WORD = sys.argv[1] if len(sys.argv) > 1 else "管家"
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
VOSK_MODEL = os.path.join(os.path.dirname(__file__), "vosk-model-small-cn")

EXIT_PHRASES = ["退出", "再见", "晚安", "休息", "拜拜", "退下"]

# ============================================
# TTS 语音合成
# ============================================
class TTS:
    def __init__(self):
        self._q = queue.Queue()
        self._engine = None
        self._running = True
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', 200)
            self._engine.setProperty('volume', 1.0)
            for v in self._engine.getProperty('voices'):
                if any(n in v.name.lower() for n in ['huihui', 'hanhan', 'yaoyao']):
                    self._engine.setProperty('voice', v.id)
                    break
        except Exception:
            self._engine = None
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        while self._running:
            try:
                text = self._q.get(timeout=0.3)
                if text and self._engine:
                    self._engine.say(text)
                    self._engine.runAndWait()
            except queue.Empty: continue

    def say(self, text, block=False):
        if not text: return
        print(f"[管家] {text}")
        if self._engine:
            if block: self._engine.say(text); self._engine.runAndWait()
            else: self._q.put(text)

# ============================================
# 语音识别（单流架构）
# ============================================
class ASR:
    def __init__(self):
        self.model = None; self.pa = None
        try:
            import vosk, pyaudio
            self.model = vosk.Model(VOSK_MODEL)
            self.pa = pyaudio.PyAudio()
        except Exception as e:
            print(f"[ASR] Vosk 不可用: {e}")

    def run(self, on_wake, on_command):
        """主循环：单流唤醒 + 命令识别"""
        import vosk, pyaudio
        stream = self.pa.open(format=pyaudio.paInt16, channels=1, rate=16000,
                              input=True, frames_per_buffer=4000)
        stream.start_stream()
        print(f"[管家] 监听唤醒词「{WAKE_WORD}」")

        wake_rec = vosk.KaldiRecognizer(self.model, 16000)
        wake_rec.SetWords(True)
        last_wake = time.time()
        listening = False
        cmd_rec = None
        cmd_text = ""
        silence_deadline = 0

        while True:
            data = stream.read(4000, exception_on_overflow=False)

            if not listening:
                # 唤醒检测
                partial = json.loads(wake_rec.PartialResult())
                triggered = WAKE_WORD in partial.get("partial", "")
                if wake_rec.AcceptWaveform(data):
                    triggered = triggered or WAKE_WORD in json.loads(wake_rec.Result()).get("text", "")

                if triggered:
                    now = time.time()
                    if now - last_wake > 2.5:
                        last_wake = now
                        listening = True
                        cmd_rec = vosk.KaldiRecognizer(self.model, 16000)
                        cmd_text = ""
                        silence_deadline = 0
                        on_wake()
            else:
                # 命令识别
                p = json.loads(cmd_rec.PartialResult())
                pt = p.get("partial", "")
                now = time.time()
                if pt and pt != cmd_text:
                    cmd_text = pt
                    print(f"\r[聆听] {cmd_text}", end="", flush=True)

                if cmd_rec.AcceptWaveform(data):
                    t = json.loads(cmd_rec.Result()).get("text", "").strip()
                    if t: cmd_text = t

                # 检测说完：有内容 + 无变化1.2秒
                if cmd_text and pt == cmd_text:
                    if silence_deadline == 0: silence_deadline = now + 1.2
                    elif now >= silence_deadline:
                        final = json.loads(cmd_rec.FinalResult()).get("text", "").strip()
                        result = final or cmd_text
                        if result:
                            print(f"\n[识别] {result}")
                            on_command(result)
                        listening = False
                        wake_rec = vosk.KaldiRecognizer(self.model, 16000)
                        wake_rec.SetWords(True)
                        cmd_rec = None; cmd_text = ""; silence_deadline = 0
                else:
                    silence_deadline = 0
                if now - (last_wake + 0.5) > 6:  # 6秒无输入退出命令模式
                    print("\n[识别] 超时")
                    listening = False
                    wake_rec = vosk.KaldiRecognizer(self.model, 16000)
                    wake_rec.SetWords(True)
                    cmd_rec = None; cmd_text = ""; silence_deadline = 0

# ============================================
# DeepSeek 问答
# ============================================
def deepseek(question):
    if not DEEPSEEK_KEY:
        return "未配置 DeepSeek 密钥"
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "你是语音助手，回答简洁口语化，3句话以内。"},
            {"role": "user", "content": question}
        ], "max_tokens": 300, "temperature": 0.7
    }).encode("utf-8")
    req = urllib.request.Request(DEEPSEEK_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        return "密钥无效" if e.code == 401 else f"请求失败({e.code})"
    except: return "查询超时"

# ============================================
# 命令解析与执行
# ============================================
APP_MAP = {
    "记事本": "notepad.exe", "计算器": "calc.exe", "画图": "mspaint.exe",
    "浏览器": "msedge.exe", "edge": "msedge.exe", "chrome": "chrome.exe",
    "谷歌": "chrome.exe", "资源管理器": "explorer.exe", "终端": "cmd.exe",
    "cmd": "cmd.exe", "powershell": "powershell.exe", "任务管理器": "taskmgr.exe",
    "word": "winword.exe", "excel": "excel.exe", "ppt": "powerpnt.exe",
    "微信": "wechat.exe", "wechat": "wechat.exe", "qq": "qq.exe",
    "设置": "ms-settings:", "截图": "snippingtool.exe",
}

def run_ps(cmd):
    """执行 PowerShell 命令"""
    try:
        r = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or r.stderr.strip() or "完成"
    except: return "执行失败"

def send_keys(*keys):
    """发送按键"""
    import ctypes; VK = {"win": 0x5B, "shift": 0x10, "ctrl": 0x11, "alt": 0x12,
        "tab": 0x09, "enter": 0x0D, "esc": 0x1B, "space": 0x20,
        "d": 0x44, "l": 0x4C, "r": 0x52, "m": 0x4D, "s": 0x53, "v": 0x56}
    for k in keys:
        code = VK.get(k.lower(), ord(k.upper()) if len(k)==1 else 0)
        if code:
            ctypes.windll.user32.keybd_event(code, 0, 0, 0)
    for k in reversed(keys):
        code = VK.get(k.lower(), ord(k.upper()) if len(k)==1 else 0)
        if code:
            ctypes.windll.user32.keybd_event(code, 0, 2, 0)

def execute(text):
    """解析并执行命令，返回回复文本"""
    t = text.strip()
    if not t: return "请说指令"

    # === 退出对话 ===
    if any(t == p for p in EXIT_PHRASES):
        return "__EXIT__"

    # === AI 问答 ===
    for pat in [r"(问下?|请问|告诉我)\s*(.+)", r"什么是\s*(.+)", r"为什么\s*(.+)",
                r"如何\s*(.+)", r"怎么\s*(.+)", r"介绍\s*(.+)"]:
        m = re.search(pat, t)
        if m:
            g = m.groups()[-1]
            print(f"[AI] 查询: {g}")
            return deepseek(g)

    # === 搜索 ===
    m = re.search(r"搜索\s*(.+)", t)
    if m:
        webbrowser.open(f"https://www.baidu.com/s?wd={m.group(1)}")
        return f"已搜索 {m.group(1)}"

    # === 打开应用 ===
    m = re.search(r"(打开|启动|运行)\s*(.+)", t)
    if m:
        target = m.group(2).strip()
        exe = APP_MAP.get(target, target)
        try:
            subprocess.Popen([exe], shell=True)
            return f"已打开 {target}"
        except:
            try: subprocess.Popen(["start", target], shell=True); return f"已尝试打开 {target}"
            except: return f"未找到 {target}"

    # === 关闭应用 ===
    m = re.search(r"(关闭|退出|结束)\s*(.+)", t)
    if m:
        target = m.group(2).strip()
        exe = APP_MAP.get(target, target)
        subprocess.run(["taskkill", "/f", "/im", exe], capture_output=True, shell=True)
        return f"已关闭 {target}"

    # === 窗口操作 ===
    if "最小化" in t: send_keys("win", "m"); return "已最小化所有窗口"
    if "显示桌面" in t: send_keys("win", "d"); return "已显示桌面"
    if "切换窗口" in t or "alt tab" in t.lower(): send_keys("alt", "tab"); return "已切换窗口"
    if "任务视图" in t: send_keys("win", "tab"); return "已打开任务视图"
    if "锁屏" in t: subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], shell=True); return "已锁屏"

    # === 系统控制 ===
    if "关机" in t: subprocess.run(["shutdown", "/s", "/t", "10"], shell=True); return "10秒后关机"
    if "重启" in t: subprocess.run(["shutdown", "/r", "/t", "10"], shell=True); return "10秒后重启"
    if "休眠" in t: subprocess.run(["shutdown", "/h"], shell=True); return "进入休眠"
    if "注销" in t: subprocess.run(["shutdown", "/l"], shell=True); return "已注销"

    # === 音量 ===
    if "静音" in t:
        try: subprocess.run(["nircmd", "mutesysvolume", "1"], shell=True)
        except: send_keys("vk57")  # VK_VOLUME_MUTE
        return "已静音"
    if "取消静音" in t:
        try: subprocess.run(["nircmd", "mutesysvolume", "0"], shell=True)
        except: send_keys("vk57")
        return "已取消静音"
    m = re.search(r"音量\s*(\d+)", t)
    if m:
        v = int(m.group(1)); v = max(0, min(100, v))
        try: subprocess.run(["nircmd", "setsysvolume", str(int(v*655.35))], shell=True)
        except: pass
        return f"音量 {v}"
    if any(w in t for w in ["调大", "增大", "声音大"]):
        try:
            for _ in range(5): subprocess.run(["nircmd", "changesysvolume", "2000"], shell=True)
        except:
            for _ in range(5): send_keys("vkAF")  # VK_VOLUME_UP
        return "音量已调大"
    if any(w in t for w in ["调小", "减小", "声音小"]):
        try:
            for _ in range(5): subprocess.run(["nircmd", "changesysvolume", "-2000"], shell=True)
        except:
            for _ in range(5): send_keys("vkAE")  # VK_VOLUME_DOWN
        return "音量已调小"

    # === 截图 ===
    if "截图" in t or "截屏" in t:
        send_keys("win", "shift", "s"); return "截图工具已启动"

    # === 时间 ===
    if re.search(r"(现在|当前).*(时间|几点)|几点了", t):
        now = datetime.now(); return f"{now.hour}点{now.minute}分"
    if re.search(r"(今天).*(星期|周).*几|星期几", t):
        return f"今天{['一','二','三','四','五','六','日'][datetime.now().weekday()]}"
    if re.search(r"(今天).*日期|几号|什么日子", t):
        now = datetime.now(); return f"{now.year}年{now.month}月{now.day}日"

    # === 天气 ===
    m = re.search(r"(.+)天气", t)
    if m:
        city = m.group(1).strip() or "北京"
        webbrowser.open(f"https://www.baidu.com/s?wd={city}+天气")
        return f"已查询 {city} 天气"

    # === 系统信息 ===
    if any(w in t for w in ["电脑信息", "系统信息", "配置"]):
        info = run_ps("Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory | Format-List")
        return info[:100]
    if "内存" in t and "使用" in t:
        info = run_ps("Get-CimInstance Win32_OperatingSystem | Select-Object @{N='Total';E={[math]::Round($_.TotalVisibleMemorySize/1MB,1)}},@{N='Free';E={[math]::Round($_.FreePhysicalMemory/1MB,1)}} | Format-List")
        return info

    # === 文件操作 ===
    m = re.search(r"(创建|新建)\s*(文件|文件夹)\s*(.+)", t)
    if m:
        name = m.group(3).strip()
        path = Path(name)
        if not path.is_absolute(): path = Path.home() / "Desktop" / name
        try:
            if "文件夹" in t: path.mkdir(parents=True, exist_ok=True); return f"已创建文件夹 {path.name}"
            else: path.touch(); return f"已创建文件 {path.name}"
        except Exception as e: return f"创建失败: {e}"

    m = re.search(r"(删除|移除)\s*(文件|文件夹)?\s*(.+)", t)
    if m:
        name = m.group(3).strip()
        path = Path(name)
        if not path.is_absolute(): path = Path.home() / "Desktop" / name
        try:
            import send2trash; send2trash.send2trash(str(path))
        except:
            try: path.unlink() if path.is_file() else __import__('shutil').rmtree(str(path))
            except Exception as e: return f"删除失败: {e}"
        return f"已删除 {path.name}"

    m = re.search(r"(打开文件|打开文档)\s*(.+)", t)
    if m:
        name = m.group(2).strip()
        path = Path(name)
        if not path.is_absolute(): path = Path.home() / "Desktop" / name
        if path.exists(): os.startfile(str(path)); return f"已打开 {path.name}"
        return f"文件不存在: {path.name}"

    # === 帮助 ===
    if any(w in t for w in ["帮助", "能做什么", "功能", "help"]):
        return ("我会：打开/关闭应用、窗口管理、音量调节、截图、时间天气、文件创建删除、"
                "搜索网页、AI问答。说「退出」回到待命状态。")

    return f"抱歉，我不理解「{t}」，试试说帮助"

# ============================================
# 主程序 — 多轮对话模式
# ============================================
def main():
    print("=" * 50)
    print("  语音管家 v3.0 — Voice Butler")
    print(f"  唤醒词: {WAKE_WORD}  对话模式: 多轮连续")
    print(f"  DeepSeek: {'已配置' if DEEPSEEK_KEY else '未配置'}")
    print("=" * 50)

    tts = TTS()
    asr = ASR()
    in_conversation = False

    def on_wake():
        nonlocal in_conversation
        print("\n>>> 唤醒 <<<")
        if not in_conversation:
            tts.say("我在，请说")
            in_conversation = True

    def on_command(text):
        nonlocal in_conversation
        result = execute(text)
        if result == "__EXIT__":
            in_conversation = False
            tts.say("好的，有需要再叫我")
        else:
            tts.say(result)

    try:
        asr.run(on_wake, on_command)
    except KeyboardInterrupt:
        print("\n管家已退出")
        tts.say("再见")

if __name__ == "__main__":
    main()
