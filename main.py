"""
语音管家 — 主程序入口（增强语音反馈版）
语音唤醒 → 语音识别 → 命令解析 → 电脑操控 → 语音反馈
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(__file__))

from wake_word import WakeWordDetector
from asr_engine import SpeechRecognizer
from command_parser import CommandParser
from action_executor import ActionExecutor
from tts_engine import SpeechSynthesizer


class VoiceButler:
    """语音管家主控"""

    def __init__(self, wake_word: str = "T3"):
        self.wake_word = wake_word
        self.detector = WakeWordDetector(wake_word=wake_word)
        self.asr = SpeechRecognizer()
        self.parser = CommandParser()
        self.executor = ActionExecutor()
        self.tts = SpeechSynthesizer()
        self._last_cmd_time = 0  # 防止重复触发

    def say(self, text: str, blocking: bool = False):
        """统一的语音反馈输出"""
        print(f"[管家语音] {text}")
        self.tts.speak(text, blocking=blocking)

    def on_wake(self):
        """唤醒后的处理流程"""
        # 防止短时间内重复触发
        now = time.time()
        if now - self._last_cmd_time < 2.0:
            return
        self._last_cmd_time = now

        print("\n" + "=" * 50)
        print("  管家已唤醒，正在聆听...")
        print("=" * 50)

        # 语音反馈：唤醒确认
        self.say("我在，请说")

        # 录音并识别
        text = self.asr.record_and_recognize(duration=5)

        if not text:
            self.say("抱歉，我没有听清，请再说一遍")
            return

        print(f"[语音识别] {text}")

        # 命令解析
        result = self.parser.parse(text)
        if result is None:
            print(f"[管家] 未识别命令: {text}")
            self.say("抱歉，我不理解这个指令。试试说「打开记事本」或「现在几点」")
            return

        cmd, params = result
        print(f"[命令识别] {cmd.name} — {cmd.description}")

        # 语音反馈：确认理解
        target = params.get("target", "")
        confirm_msg = cmd.description
        if target:
            confirm_msg = f"好的，{cmd.description.replace('应用程序', target).replace('搜索', f'搜索 {target}')}"
        self.say(f"收到。{cmd.description}")

        # 特殊处理帮助命令
        if cmd.name == "help":
            help_text = self.parser.get_help()
            print(help_text)
            self.say("已显示帮助信息，请看屏幕")
            return

        # 执行命令
        print(f"[执行中] {cmd.name} ...")
        exec_result = self.executor.execute(cmd.name, params, text)
        print(f"[执行结果] {exec_result}")

        # 语音反馈：执行结果
        self.say(exec_result)

    def run(self):
        """启动语音管家"""
        print("=" * 50)
        print("  语音管家 v1.1 — Voice Butler")
        print(f"  唤醒词: {self.wake_word}")
        print("  语音反馈: 已启用")
        print("=" * 50)
        print(self.parser.get_help())
        print("\n等待唤醒...")

        # 启动语音播报
        def delayed_welcome():
            time.sleep(0.5)
            self.say(f"语音管家已启动，对我说 {self.wake_word} 来唤醒我")

        threading.Thread(target=delayed_welcome, daemon=True).start()

        try:
            self.detector.start(callback=self.on_wake)
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n管家已退出")
            self.say("管家已退出，再见")
            self.detector.stop()


def main():
    wake_word = sys.argv[1] if len(sys.argv) > 1 else "T3"
    butler = VoiceButler(wake_word=wake_word)
    butler.run()


if __name__ == "__main__":
    main()
