"""
语音管家 v3.0 — 多轮对话 + 完整电脑操控
唤醒词 → 进入对话模式 → 连续发指令 → 说"退出"回到监听
"""

import sys, os, json, time, queue, threading, subprocess, re
import urllib.request, urllib.error
from command_parser import CommandParser
from action_executor import ActionExecutor

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
        last_activity = 0           # 最后一次有意义的语音变化时刻
        IDLE_TIMEOUT = 15           # 超时秒数（进入命令模式后完全无语音活动则退出）
        SILENCE_GAP = 1.0           # 停顿检测秒数（用户说完后判定结束）

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
                        last_activity = now
                        cmd_rec = vosk.KaldiRecognizer(self.model, 16000)
                        cmd_text = ""
                        on_wake()
            else:
                # 命令识别
                p = json.loads(cmd_rec.PartialResult())
                pt = p.get("partial", "")
                now = time.time()
                if pt and pt != cmd_text:
                    cmd_text = pt
                    last_activity = now
                    print(f"\r[聆听] {cmd_text}", end="", flush=True)

                if cmd_rec.AcceptWaveform(data):
                    t = json.loads(cmd_rec.Result()).get("text", "").strip()
                    if t:
                        cmd_text = t
                        last_activity = now

                # 检测说完：有内容 + 停顿超过 SILENCE_GAP 秒
                if cmd_text and now - last_activity >= SILENCE_GAP:
                    # 再次确认不是瞬时波动
                    time.sleep(0.15)
                    final = json.loads(cmd_rec.FinalResult()).get("text", "").strip()
                    result = final or cmd_text
                    if result:
                        print(f"\n[识别] {result}")
                        on_command(result)
                    else:
                        # FinalResult 为空但之前有 partial，用最后的 partial
                        if cmd_text:
                            print(f"\n[识别] {cmd_text}")
                            on_command(cmd_text)
                    listening = False
                    wake_rec = vosk.KaldiRecognizer(self.model, 16000)
                    wake_rec.SetWords(True)
                    cmd_rec = None; cmd_text = ""; silence_deadline = 0
                    continue

                # 超时检测：进入命令模式后完全无语音活动超时退出
                idle = now - last_activity
                if idle >= IDLE_TIMEOUT and not cmd_text:
                    print("\n[识别] 超时（未检测到语音）")
                    listening = False
                    wake_rec = vosk.KaldiRecognizer(self.model, 16000)
                    wake_rec.SetWords(True)
                    cmd_rec = None; cmd_text = ""
                elif idle >= 10 and not cmd_text:
                    # 10秒时给个提示
                    pass  # 静默等待，不给干扰提示

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
parser = CommandParser()
executor = ActionExecutor()

def execute(text):
    """解析并执行命令，返回回复文本"""
    t = text.strip()
    if not t:
        return "请说指令"

    if any(t == p or t.startswith(p + " ") for p in EXIT_PHRASES):
        return "__EXIT__"

    # 优先走命令解析器 + 执行器
    parsed = parser.parse(t)
    if parsed:
        cmd, params = parsed
        if cmd.name == "help":
            return parser.get_help()
        try:
            result = executor.execute(cmd.name, params, t)
            if result:
                return result
            # 命令已匹配但 handler 返回空 → AI 兜底（如 ai_query）
            if cmd.name == "ai_query":
                question = params.get("target", t).strip()
                if question:
                    return deepseek(question)
                return "请说你想问什么"
            return f"已执行 {cmd.description}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"执行失败: {e}"

    # 命令解析器完全未命中 → 尝试 AI
    question = re.sub(r"^(问下?|请问|告诉我|什么是|为什么|如何|怎么|介绍)\s*", "", t)
    if question and question != t:
        return deepseek(question)
    return f"抱歉，我不理解「{t}」"

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
