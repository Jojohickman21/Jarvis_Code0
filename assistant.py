# assistant.py — JARVIS Voice Assistant (CLEAN VERSION)

from __future__ import annotations
from google_actions import GoogleActions

import json
import os
import tempfile
import threading
import time
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

# ─── Personality ───────────────────────────────────────────────
def load_personalities(path="personality.json"):
    with open(path, "r") as f:
        return json.load(f)["personality_profiles"]

# ─── Assistant ─────────────────────────────────────────────────
class VoiceAssistant:

    def __init__(self):
        self.personalities = load_personalities()
        self._personality = self.personalities[DEFAULT_PERSONALITY]

        self.conversation = [
            {"role": "system", "content": self._personality["system_prompt"]}
        ]

        self._pa = pyaudio.PyAudio()

    # ── AUDIO OUTPUT (I2S) ─────────────────────────────────────
    def _play_audio(self, filepath):
        subprocess.run([
            "aplay",
            "-D", "plughw:2,0",
            filepath
        ])

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
            rms = np.sqrt(np.mean(np.frombuffer(data, dtype=np.int16) ** 2))

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
        with open(path, "rb") as f:
            result = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=f
            )
        text = result.text.strip()
        print(f"👤 {text}")
        return text

    # ── THINK ────────────────────────────────────────────────
    def think(self, text):
        self.conversation.append({"role": "user", "content": text})

        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=self.conversation
        )

        reply = response.choices[0].message.content
        print(f"🤖 {reply}")

        self.conversation.append({"role": "assistant", "content": reply})
        return reply

    # ── SPEAK ────────────────────────────────────────────────
    def speak(self, text):
        if elevenlabs_client is None:
            print(text)
            return

        audio = elevenlabs_client.text_to_speech.convert(
            voice_id="EXAVITQu4vr4xnSDxMaL",
            text=text,
            model_id="eleven_multilingual_v2"
        )

        audio_bytes = b"".join(audio)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            tmp.write(audio_bytes)
            mp3_path = tmp.name

        wav_path = mp3_path.replace(".mp3", ".wav")

        subprocess.run([
            "ffmpeg", "-y", "-i", mp3_path, wav_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self._play_audio(wav_path)

        os.remove(mp3_path)
        os.remove(wav_path)

    # ── MAIN LOOP ─────────────────────────────────────────────
    def run(self):
        print("🚀 JARVIS ONLINE")

        while True:
            audio = self.record()
            text = self.transcribe(audio)
            reply = self.think(text)
            self.speak(reply)