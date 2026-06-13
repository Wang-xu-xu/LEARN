"""
语音管家 — 主程序入口
语音唤醒 → 语音识别 → 命令解析 → 电脑操控 → 语音反馈
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from wake_word import WakeWordDetector
from asr_engine import SpeechRecognizer
from command_parser import CommandParser
from action_executor import ActionExecutor
from tts_engine import SpeechSynthesizer


class VoiceButler:
    """语音管家主控"""

    def __init__(self, wake_word: str = "hey_jarvis"):
        self.wake_word = wake_word
        self.detector = WakeWordDetector(wake_word=wake_word)
        self.asr = SpeechRecognizer()
        self.parser = CommandParser()
        self.executor = ActionExecutor()
        self.tts = SpeechSynthesizer()

    def on_wake(self):
        """唤醒后的处理流程"""
        print("\n" + "=" * 50)
        print("  管家已唤醒，正在聆听...")
        print("=" * 50)

        response = self.tts
        response.speak("我在，请说")

        # 录音并识别
        text = self.asr.record_and_recognize(duration=5)

        if not text:
            msg = "抱歉，我没有听清，请再说一遍"
            print(f"[管家] {msg}")
            self.tts.speak(msg)
            return

        print(f"[语音识别] {text}")

        # 命令解析
        result = self.parser.parse(text)
        if result is None:
            msg = f"未识别命令: {text}"
            print(f"[管家] {msg}")
            self.tts.speak("抱歉，我不理解这个指令")
            return

        cmd, params = result
        print(f"[命令识别] {cmd.name} — {cmd.description}")

        # 特殊处理帮助命令
        if cmd.name == "help":
            help_text = self.parser.get_help()
            print(help_text)
            self.tts.speak("已显示帮助信息")
            return

        # 执行命令
        exec_result = self.executor.execute(cmd.name, params, text)
        print(f"[执行结果] {exec_result}")
        self.tts.speak(exec_result)

    def run(self):
        """启动语音管家"""
        print("=" * 50)
        print("  语音管家 v1.0 — Voice Butler")
        print(f"  唤醒词: {self.wake_word}")
        print("=" * 50)
        print(self.parser.get_help())
        print("\n等待唤醒...")

        try:
            self.detector.start(callback=self.on_wake)
            # 保持主线程
            while True:
                import time
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n管家已退出")
            self.detector.stop()


def main():
    wake_word = sys.argv[1] if len(sys.argv) > 1 else "hey_jarvis"
    butler = VoiceButler(wake_word=wake_word)
    butler.run()


if __name__ == "__main__":
    main()
