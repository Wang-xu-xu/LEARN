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
    """语音唤醒词检测器 — 支持自定义唤醒词（关键词匹配模式）"""

    BUILTIN_MODELS = [
        "alexa", "hey_mycroft", "hey_jarvis",
        "weather", "timer", "xbox", "hey_marvis",
    ]

    def __init__(self, wake_word: str = "T3", sensitivity: float = 0.5):
        self.wake_word = wake_word
        self.sensitivity = sensitivity
        self._running = False
        self._callback = None
        self._model = None
        self._use_keyword_mode = False  # 自定义唤醒词用关键词模式
        self._thread = None

    def _load_model(self):
        """加载唤醒词检测模型"""
        # 判断是否使用内置模型还是自定义关键词模式
        if self.wake_word not in self.BUILTIN_MODELS:
            print(f"[唤醒] '{self.wake_word}' 为自定义唤醒词，使用持续监听+关键词检测模式")
            self._use_keyword_mode = True
            return self._init_keyword_mode()

        # 内置模型：使用 openWakeWord
        try:
            from openwakeword.model import Model
            import openwakeword.utils
            model_dir = os.path.join(os.path.dirname(__file__), "wake_models")
            os.makedirs(model_dir, exist_ok=True)
            openwakeword.utils.download_models(target_directory=model_dir)

            model_path = os.path.join(model_dir, f"{self.wake_word}.onnx")
            if not os.path.exists(model_path):
                model_path = os.path.join(model_dir, "alexa.onnx")
                print(f"[唤醒] 未找到 '{self.wake_word}' 模型，使用 'alexa' 替代")

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

    def _keyword_listen_loop(self):
        """关键词检测模式 — 低延迟持续监听自定义唤醒词"""
        print(f"[唤醒] 持续监听关键词 '{self.wake_word}' ...")

        try:
            import speech_recognition as sr
            r = sr.Recognizer()
            r.energy_threshold = 80        # 降低阈值，更灵敏
            r.dynamic_energy_threshold = True  # 动态调整
            r.pause_threshold = 0.4        # 缩短停顿检测，更快截断
            r.operation_timeout = 0.3      # 内部操作超时
            r.non_speaking_duration = 0.3  # 非语音判定间隔

            with sr.Microphone(sample_rate=16000) as source:
                # 快速噪音校准
                r.adjust_for_ambient_noise(source, duration=0.5)
                print("[唤醒] 噪音校准完成 (阈值动态)，开始监听")

                last_wake = 0
                while self._running:
                    try:
                        # 缩短超时和最大录音时长，提高轮询频率
                        audio = r.listen(source, timeout=0.5, phrase_time_limit=2)
                        now_ts = time.time()
                        if now_ts - last_wake < 2.0:
                            continue  # 冷却期，跳过识别避免重复

                        try:
                            text = r.recognize_google(audio, language="zh-CN").lower()
                            if self.wake_word.lower() in text:
                                print(f"[唤醒] 检测到关键词 '{self.wake_word}'!")
                                last_wake = time.time()
                                if self._callback:
                                    threading.Thread(target=self._callback, daemon=True).start()
                        except sr.UnknownValueError:
                            pass
                        except sr.RequestError:
                            time.sleep(0.2)  # 网络错误时稍等再重试
                    except sr.WaitTimeoutError:
                        continue
        except ImportError:
            print("[唤醒] SpeechRecognition 不可用，降级到键盘模式")
            self._keyboard_mode()

    def _init_keyword_mode(self):
        """初始化关键词检测模式"""
        try:
            import speech_recognition
            print("[唤醒] 关键词检测模式就绪")
            return True
        except ImportError:
            print("[唤醒] 需安装: pip install SpeechRecognition pyaudio")
            return False

    def _keyboard_mode(self):
        """键盘模拟模式 — 按 Enter 键模拟唤醒"""
        print("\n" + "=" * 50)
        print(f"  语音管家 — 键盘模拟模式 (唤醒词: {self.wake_word})")
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
            if self._use_keyword_mode:
                self._thread = threading.Thread(target=self._keyword_listen_loop, daemon=True)
            else:
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
