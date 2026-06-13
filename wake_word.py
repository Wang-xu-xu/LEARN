"""
语音管家 — 唤醒词检测模块
基于 openWakeWord，免费开源，支持 "hey jarvis" 等内置唤醒词
"""

import os
import sys
import threading
import time
from collections import deque


class WakeWordDetector:
    """语音唤醒词检测器"""

    DEFAULT_MODEL = "hey_jarvis"  # openWakeWord 内置模型之一
    AVAILABLE_MODELS = [
        "alexa", "hey_mycroft", "hey_jarvis",
        "weather", "timer", "xbox", "hey_marvis",
    ]

    def __init__(self, wake_word: str = "hey_jarvis", sensitivity: float = 0.5):
        self.wake_word = wake_word
        self.sensitivity = sensitivity
        self._running = False
        self._callback = None
        self._model = None
        self._thread = None

    def _load_model(self):
        """动态加载 openWakeWord 模型"""
        try:
            from openwakeword.model import Model
            # 下载内置模型（首次运行自动下载）
            import openwakeword.utils
            model_dir = os.path.join(os.path.dirname(__file__), "wake_models")
            os.makedirs(model_dir, exist_ok=True)
            openwakeword.utils.download_models(target_directory=model_dir)

            model_path = os.path.join(model_dir, f"{self.wake_word}.onnx")
            if not os.path.exists(model_path):
                # 尝试用 alexa 作为 fallback
                model_path = os.path.join(model_dir, "alexa.onnx")
                print(f"[唤醒] 未找到 '{self.wake_word}' 模型，使用 'alexa' 替代")
                self.wake_word = "alexa"

            self._model = Model(
                wakeword_models=[model_path],
            )
            print(f"[唤醒] 模型加载成功，唤醒词: {self.wake_word}")
            return True
        except ImportError:
            print("[唤醒] openWakeWord 未安装，使用键盘模拟模式")
            print("       安装: pip install openwakeword")
            return False
        except Exception as e:
            print(f"[唤醒] 模型加载失败: {e}")
            return False

    def _listen_loop(self):
        """监听循环 — 从麦克风读取音频并检测唤醒词"""
        try:
            import pyaudio
            import numpy as np

            p = pyaudio.PyAudio()
            rate = 16000
            chunk = 1280  # 80ms at 16kHz

            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                frames_per_buffer=chunk,
            )
            print(f"[唤醒] 开始监听，等待唤醒词 '{self.wake_word}' ...")

            while self._running:
                audio_data = stream.read(chunk, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

                prediction = self._model.predict(audio_array)
                for model_name, score in prediction.items():
                    if score > self.sensitivity:
                        print(f"[唤醒] 检测到唤醒词! ({model_name}: {score:.2f})")
                        if self._callback:
                            threading.Thread(target=self._callback, daemon=True).start()
                        # 唤醒后短暂冷却，避免重复触发
                        time.sleep(2)

            stream.stop_stream()
            stream.close()
            p.terminate()

        except ImportError:
            print("[唤醒] pyaudio 未安装。进入键盘模拟模式...")
            self._keyboard_mode()

    def _keyboard_mode(self):
        """键盘模拟模式 — 按空格键模拟唤醒"""
        print("\n" + "=" * 50)
        print("  语音管家 — 键盘模拟模式")
        print("  按 Enter 键模拟唤醒")
        print("=" * 50)
        while self._running:
            try:
                input("\n按 Enter 唤醒管家 > ")
                if self._callback:
                    self._callback()
            except (EOFError, KeyboardInterrupt):
                break

    def start(self, callback):
        """启动唤醒词检测"""
        self._callback = callback
        self._running = True

        if self._load_model():
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
        else:
            self._thread = threading.Thread(target=self._keyboard_mode, daemon=True)
            self._thread.start()

    def stop(self):
        """停止检测"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
