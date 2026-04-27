# assistant.py — FINAL VERSION (JARVIS + AI EMOTION SYSTEM)

from __future__ import annotations

import json
import os
import tempfile
import wave
import subprocess

import numpy as np
import pyaudio
from dotenv import load_dotenv
from openai import OpenAI

from config import (
    DEFAULT_PERSONALITY,
    OPENAI_MODEL,
    RECORD_SECONDS_MAX,
    SAMPLE_RATE,
    SILENCE_DURATION,
    SILENCE_THRESHOLD,
    TEMP_AUDIO_PATH,
)

# ─── Setup ─────────────────────────────────────────────────────
load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    from elevenlabs import ElevenLabs
    elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
except:
    elevenlabs_client = None
    print("[WARN] ElevenLabs not available")


def load_personalities(path="personality.json"):
    with open(path, "r") as f:
        return json.load(f)["personality_profiles"]


class VoiceAssistant:

    def __init__(self):
        self.personalities = load_personalities()
        self._personality_name = DEFAULT_PERSONALITY
        self._personality = self.personalities[self._personality_name]

        self._pa = pyaudio.PyAudio()

    # ── SET PERSONALITY ─────────────────────────────────────────
    def set_personality(self, name):
        if name in self.personalities:
            if name != self._personality_name:
                print(f"[INFO] Switching personality → {name}")
            self._personality_name = name
            self._personality = self.personalities[name]

    # ── AUDIO OUTPUT ───────────────────────────────────────────
    def _play_audio(self, filepath):
        subprocess.run(["aplay", "-D", "plughw:2,0", filepath])

    # ── RECORD ────────────────────────────────────────────────
    def record(self):
        chunk = 1024

        stream = self._pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=chunk,
        )

        print("🎤 Listening...")
        frames = []
        silent = 0

        for _ in range(int(SAMPLE_RATE / chunk * RECORD_SECONDS_MAX)):
            data = stream.read(chunk, exception_on_overflow=False)

            samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            rms = np.sqrt(np.mean(samples ** 2))

            frames.append(data)

            if rms < SILENCE_THRESHOLD:
                silent += 1
                if silent > int(SILENCE_DURATION * SAMPLE_RATE / chunk):
                    break
            else:
                silent = 0

        stream.stop_stream()
        stream.close()

        with wave.open(TEMP_AUDIO_PATH, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))

        return TEMP_AUDIO_PATH

    # ── TRANSCRIBE ────────────────────────────────────────────
    def transcribe(self, path):
        try:
            with open(path, "rb") as f:
                result = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f
                )
            text = result.text.strip()
            print(f"👤 {text}")
            return text
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")
            return None

    # ── THINK (AI EMOTION SYSTEM) ─────────────────────────────
    def think(self, text):
        try:
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""
You are an AI that MUST respond in JSON format ONLY.

Choose the most appropriate emotion for the response from:
- happy_excited
- angry
- scared
- sad_tired
- disgusted

Return JSON in this exact format:
{{
  "emotion": "...",
  "response": "..."
}}

User input: {text}
"""
                    }
                ]
            )

            content = response.choices[0].message.content.strip()
            data = json.loads(content)

            emotion = data.get("emotion", DEFAULT_PERSONALITY)
            reply = data.get("response", "Something went wrong.")

            print(f"🤖 [{emotion}] {reply}")

            return emotion, reply

        except Exception as e:
            print(f"[ERROR] GPT failed: {e}")
            return DEFAULT_PERSONALITY, "Something went wrong."

    # ── SPEAK (PERSONALITY VOICE) ─────────────────────────────
    def speak(self, text):
        if elevenlabs_client is None:
            print(text)
            return

        voice_cfg = self._personality.get("voice", {})

        audio = elevenlabs_client.text_to_speech.convert(
            voice_id=voice_cfg.get("voice_id"),
            text=text,
            model_id=voice_cfg.get("model_id"),
            voice_settings=voice_cfg.get("settings"),
        )

        audio_bytes = b"".join(audio)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio_bytes)
            mp3_path = tmp.name

        wav_path = mp3_path.replace(".mp3", ".wav")

        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, wav_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        self._play_audio(wav_path)

        os.remove(mp3_path)
        os.remove(wav_path)

    # ── MAIN LOOP ─────────────────────────────────────────────
    def run(self):
        print("🚀 JARVIS ONLINE (AI EMOTION ENABLED)")

        try:
            while True:
                audio = self.record()
                text = self.transcribe(audio)

                if not text:
                    continue

                # 🔥 JARVIS DETECTION
                if "jarvis" not in text.lower():
                    print("[DEBUG] No 'jarvis' detected\n")
                    continue

                print("🟢 Jarvis detected!")

                clean_text = text.lower().replace("jarvis", "").strip()

                emotion, reply = self.think(clean_text)

                self.set_personality(emotion)
                self.speak(reply)

                print()

        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")

        finally:
            self._pa.terminate()