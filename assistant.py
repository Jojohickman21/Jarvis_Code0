# assistant.py — JARVIS Voice Assistant

from __future__ import annotations
from google_actions import GoogleActions

import io
import json
import math
import os
import struct
import tempfile
import threading
import time
import wave
import subprocess
from pathlib import Path

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
    WAKE_WORD,
)

# ─── Load environment & API clients ────────────────────────────
load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ElevenLabs
try:
    from elevenlabs import ElevenLabs
    elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
except Exception:
    elevenlabs_client = None
    print("[WARN] ElevenLabs SDK not available — TTS will fall back to pyttsx3.")

# ─── Personality loader ────────────────────────────────────────
def load_personalities(path: str = "personality.json") -> dict:
    with open(path, "r") as f:
        data = json.load(f)
    return data.get("personality_profiles", {})

# ─── Voice Assistant ───────────────────────────────────────────
class VoiceAssistant:

    def __init__(self, servo_controller=None, motion_player=None, personality_name: str = DEFAULT_PERSONALITY):
        self.personalities = load_personalities()
        self._personality_name = personality_name
        self._personality = self.personalities.get(personality_name)

        if self._personality is None:
            self._personality_name = DEFAULT_PERSONALITY
            self._personality = self.personalities[DEFAULT_PERSONALITY]

        self.conversation = []
        self._rebuild_system_message()

        self.servo_controller = servo_controller
        self.motion_player = motion_player

        try:
            self.google = GoogleActions()
        except Exception:
            self.google = None

        self._pa = pyaudio.PyAudio()
        self._lock = threading.Lock()

    # ── AUDIO OUTPUT (UPDATED) ─────────────────────────────────

    def _play_audio_file(self, filepath: str):
        """Play audio through ALSA (I2S amp)."""
        try:
            subprocess.run([
                "aplay",
                "-D", "default",   # change to hw:2,0 if needed
                filepath
            ], check=True)
        except Exception as e:
            print(f"[ERROR] aplay failed: {e}")

    # ── SPEAK (UPDATED) ────────────────────────────────────────

    def speak(self, text: str):
        voice_cfg = self._personality.get("voice", {})
        voice_id = voice_cfg.get("voice_id", "EXAVITQu4vr4xnSDxMaL")
        model_id = voice_cfg.get("model_id", "eleven_multilingual_v2")
        settings = voice_cfg.get("settings", {})

        if elevenlabs_client is None:
            self._speak_fallback(text)
            return

        try:
            audio_generator = elevenlabs_client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=model_id,
                voice_settings={
                    "stability": settings.get("stability", 0.5),
                    "similarity_boost": settings.get("similarity_boost", 0.75),
                    "style": settings.get("style", 0.5),
                    "use_speaker_boost": settings.get("use_speaker_boost", True),
                },
            )

            audio_bytes = b"".join(audio_generator)

            # 🔥 Save to temp WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            # 🔥 Convert to WAV (aplay prefers wav)
            wav_path = tmp_path.replace(".mp3", ".wav")
            subprocess.run([
                "ffmpeg", "-y", "-i", tmp_path, wav_path
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # 🔥 Play via ALSA
            self._play_audio_file(wav_path)

            os.remove(tmp_path)
            os.remove(wav_path)

        except Exception as exc:
            print(f"[ERROR] ElevenLabs TTS failed: {exc}")
            self._speak_fallback(text)

    # ── FALLBACK ───────────────────────────────────────────────

    def _speak_fallback(self, text: str):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
        except Exception:
            print(text)

    # ── KEEP EVERYTHING ELSE THE SAME ──────────────────────────
    # (record_speech, transcribe, think, emote, run, etc.)