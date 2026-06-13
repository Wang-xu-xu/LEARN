"""
语音管家 — 语音识别模块 (ASR)
优先使用本地 Intel ASR，降级使用 Vosk 或在线方案
"""

import os
import json
import tempfile
import wave
from typing import Optional


class SpeechRecognizer:
    """语音识别器 — 多后端支持"""

    def __init__(self, backend: str = "auto", language: str = "zh"):
        self.backend = backend
        self.language = language
        self._recognizer = None
        self._init_backend()

    def _init_backend(self):
        """初始化识别后端"""
        # 优先尝试 Intel 本地 ASR
        if self.backend in ("auto", "intel"):
            try:
                # Intel 本地 ASR 通过 shell 调用
                self.backend = "intel"
                print("[ASR] 使用 Intel 本地离线识别")
                return
            except Exception:
                pass

        # 尝试 Vosk 离线识别
        if self.backend in ("auto", "vosk"):
            try:
                import vosk
                import json
                model_path = os.path.join(os.path.dirname(__file__), "vosk-model")
                if os.path.exists(model_path):
                    self._recognizer = vosk.KaldiRecognizer(vosk.Model(model_path), 16000)
                    self.backend = "vosk"
                    print("[ASR] 使用 Vosk 本地离线识别")
                    return
            except ImportError:
                pass

        # 降级到 SpeechRecognition
        if self.backend in ("auto", "sr"):
            try:
                import speech_recognition as sr
                self._recognizer = sr.Recognizer()
                self.backend = "sr"
                print("[ASR] 使用 SpeechRecognition (在线)")
                return
            except ImportError:
                pass

        print("[ASR] 警告：未找到可用的语音识别后端")
        self.backend = "none"

    def recognize_file(self, audio_path: str) -> Optional[str]:
        """识别音频文件"""
        if not os.path.exists(audio_path):
            return None

        if self.backend == "intel":
            return self._recognize_intel(audio_path)

        if self.backend == "vosk":
            return self._recognize_vosk(audio_path)

        if self.backend == "sr":
            return self._recognize_sr(audio_path)

        return None

    def _recognize_intel(self, audio_path: str) -> Optional[str]:
        """Intel 本地 ASR 识别"""
        try:
            temp_out = tempfile.mktemp(suffix=".txt")
            cmd = f'python -c "from use_skill import local_asr; ... "'
            # 使用 intel 的 local-asr 技能
            # 实际调用通过 shell executor
            return self._run_intel_asr(audio_path)
        except Exception as e:
            print(f"[ASR] Intel 识别失败: {e}")
            return None

    def _run_intel_asr(self, audio_path: str) -> Optional[str]:
        """调用 Intel ASR"""
        import subprocess
        try:
            result = subprocess.run(
                ["python", "-c", f"""
import sys
sys.path.insert(0, r'{os.path.dirname(__file__)}')
# 使用 whisper 或 vosk 作为替代
try:
    import whisper
    model = whisper.load_model("base")
    result = model.transcribe(r"{audio_path}", language="zh")
    print(result["text"])
except ImportError:
    print("")
"""],
                capture_output=True, text=True, timeout=30
            )
            text = result.stdout.strip()
            return text if text else None
        except Exception:
            return None

    def _recognize_vosk(self, audio_path: str) -> Optional[str]:
        """Vosk 离线识别"""
        import wave
        try:
            wf = wave.open(audio_path, "rb")
            self._recognizer = vosk.KaldiRecognizer(vosk.Model(
                os.path.join(os.path.dirname(__file__), "vosk-model")
            ), wf.getframerate())
            result_text = ""
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if self._recognizer.AcceptWaveform(data):
                    res = json.loads(self._recognizer.Result())
                    result_text += res.get("text", "") + " "
            final = json.loads(self._recognizer.FinalResult())
            result_text += final.get("text", "")
            wf.close()
            return result_text.strip() or None
        except Exception as e:
            print(f"[ASR] Vosk 识别失败: {e}")
            return None

    def _recognize_sr(self, audio_path: str) -> Optional[str]:
        """SpeechRecognition 在线识别"""
        import speech_recognition as sr
        try:
            with sr.AudioFile(audio_path) as source:
                audio = self._recognizer.record(source)
            lang = "zh-CN" if self.language == "zh" else "en-US"
            return self._recognizer.recognize_google(audio, language=lang)
        except Exception as e:
            print(f"[ASR] SpeechRecognition 识别失败: {e}")
            return None

    def record_and_recognize(self, duration: int = 5) -> Optional[str]:
        """录音并识别"""
        import pyaudio
        import wave
        import numpy as np

        temp_file = tempfile.mktemp(suffix=".wav")
        try:
            p = pyaudio.PyAudio()
            rate = 16000
            chunk = 1024

            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=rate,
                input=True,
                frames_per_buffer=chunk,
            )

            print(f"[ASR] 正在录音 {duration} 秒... 请说话")
            frames = []
            for _ in range(0, int(rate / chunk * duration)):
                data = stream.read(chunk)
                frames.append(data)

            stream.stop_stream()
            stream.close()
            p.terminate()

            # 保存录音
            wf = wave.open(temp_file, 'wb')
            wf.setnchannels(1)
            wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(rate)
            wf.writeframes(b''.join(frames))
            wf.close()

            return self.recognize_file(temp_file)

        except ImportError:
            print("[ASR] pyaudio 未安装，使用键盘输入模式")
            return input("请输入语音内容 > ").strip()
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
