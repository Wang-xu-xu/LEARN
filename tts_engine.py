"""
语音管家 — 语音合成模块 (TTS) 低延迟版
使用语音队列 + 专用线程，消除单次 TTS 线程创建开销
"""

import os
import threading
import queue


class SpeechSynthesizer:
    """语音合成器 — 后台队列异步朗读"""

    def __init__(self, backend: str = "auto", language: str = "zh"):
        self.backend = backend
        self.language = language
        self._engine = None
        self._speech_queue = queue.Queue()
        self._worker_running = True
        self._init_backend()
        # 启动专用 TTS 工作线程
        self._worker = threading.Thread(target=self._speech_worker, daemon=True)
        self._worker.start()

    def _init_backend(self):
        """初始化 TTS 后端"""
        if self.backend in ("auto", "pyttsx3"):
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                voices = self._engine.getProperty('voices')
                best_voice = None
                for voice in voices:
                    name_lower = voice.name.lower()
                    if "huihui" in name_lower or "hanhan" in name_lower or "yaoyao" in name_lower:
                        best_voice = voice.id
                        break
                    if "chinese" in name_lower or "zh" in voice.id.lower():
                        if not best_voice:
                            best_voice = voice.id

                if best_voice:
                    self._engine.setProperty('voice', best_voice)

                self._engine.setProperty('rate', 200)    # 加速到 200，减少语速延迟
                self._engine.setProperty('volume', 1.0)
                self.backend = "pyttsx3"
                return
            except ImportError:
                pass

        print("[TTS] 警告：无可用语音引擎")
        self.backend = "none"

    def _speech_worker(self):
        """后台线程：从队列取文本并朗读"""
        while self._worker_running:
            try:
                text = self._speech_queue.get(timeout=0.5)
                if text and self._engine:
                    self._engine.say(text)
                    self._engine.runAndWait()
            except queue.Empty:
                continue
            except Exception:
                pass

    def speak(self, text: str, blocking: bool = False):
        """朗读文本（默认非阻塞，直接入队列）"""
        if not text or not text.strip():
            return
        if self.backend == "none":
            print(f"[TTS] {text}")
            return
        if blocking:
            # 阻塞模式：跳过队列，直接朗读
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:
                pass
        else:
            self._speech_queue.put(text)

    def stop(self):
        """停止 TTS"""
        self._worker_running = False

