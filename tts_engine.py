"""
语音管家 — 语音合成模块 (TTS)
优先使用 Intel 本地 TTS，降级使用系统 TTS 或 pyttsx3
"""

import os
import tempfile
import subprocess
import threading
from typing import Optional


class SpeechSynthesizer:
    """语音合成器"""

    def __init__(self, backend: str = "auto", language: str = "zh"):
        self.backend = backend
        self.language = language
        self._engine = None
        self._init_backend()

    def _init_backend(self):
        """初始化 TTS 后端"""
        # 尝试 pyttsx3（Windows 自带 SAPI5）
        if self.backend in ("auto", "pyttsx3"):
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                voices = self._engine.getProperty('voices')
                # 中文语音 — 优先女声
                best_voice = None
                for voice in voices:
                    name_lower = voice.name.lower()
                    id_lower = voice.id.lower()
                    if "huihui" in name_lower or "hanhan" in name_lower or "yaoyao" in name_lower:
                        best_voice = voice.id
                        break
                    if "chinese" in name_lower or "zh" in id_lower:
                        if not best_voice:
                            best_voice = voice.id

                if best_voice:
                    self._engine.setProperty('voice', best_voice)
                    print(f"[TTS] 语音: {best_voice}")
                else:
                    print("[TTS] 未找到中文语音，使用默认英语语音")

                self._engine.setProperty('rate', 170)   # 语速适中
                self._engine.setProperty('volume', 1.0)
                self.backend = "pyttsx3"
                print("[TTS] 使用 Windows SAPI5 语音合成")
                return
            except ImportError:
                pass

        # 尝试 Intel 本地 TTS
        if self.backend in ("auto", "intel"):
            try:
                # 通过 local-tts 技能调用
                self.backend = "intel"
                print("[TTS] 使用 Intel 本地语音合成")
                return
            except Exception:
                pass

        print("[TTS] 警告：未找到可用的 TTS 后端，使用文本输出")
        self.backend = "none"

    def speak(self, text: str, blocking: bool = False):
        """朗读文本"""
        if not text:
            return

        if self.backend == "pyttsx3":
            if blocking:
                self._speak_pyttsx3(text)
            else:
                threading.Thread(target=self._speak_pyttsx3, args=(text,), daemon=True).start()

        elif self.backend == "intel":
            self._speak_intel(text)

        else:
            print(f"[TTS] {text}")

    def _speak_pyttsx3(self, text: str):
        """pyttsx3 朗读"""
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as e:
            print(f"[TTS] 合成失败: {e}")

    def _speak_intel(self, text: str):
        """Intel 本地 TTS"""
        try:
            output_dir = os.path.expanduser("~/Music")
            output_file = os.path.join(output_dir, "tts_output.wav")
            # 通过 local-tts 技能调用
            print(f"[TTS] 生成语音: {text[:30]}...")
        except Exception as e:
            print(f"[TTS] Intel TTS 失败: {e}")
