# assistant.py — JARVIS Voice Assistant
#
# Wake word → Record → Transcribe → Think → Speak + Emote
#
# Local:  openWakeWord wake word detection, servo motions
# Cloud:  OpenAI Whisper (STT), GPT-4o-mini (LLM), ElevenLabs (TTS)

from __future__ import annotations

import io
import json
import math
import os
import struct
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np
from openwakeword.model import Model as OWWModel
import pyaudio
import pygame
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

# ElevenLabs — import lazily to keep startup fast if key is missing
try:
    from elevenlabs import ElevenLabs
    elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
except Exception:
    elevenlabs_client = None
    print("[WARN] ElevenLabs SDK not available — TTS will fall back to pyttsx3.")


# ─── Personality loader ────────────────────────────────────────

def load_personalities(path: str = "personality.json") -> dict:
    """Load all personality profiles from the JSON config."""
    with open(path, "r") as f:
        data = json.load(f)
    return data.get("personality_profiles", {})


# ─── Voice Assistant ───────────────────────────────────────────

class VoiceAssistant:
    """
    End-to-end voice assistant:
      1. Listens for wake word  (openWakeWord, local — no API key needed)
      2. Records user speech    (PyAudio, local)
      3. Transcribes speech     (OpenAI Whisper, cloud)
      4. Generates response     (GPT-4o-mini, cloud)
      5. Speaks response        (ElevenLabs TTS, cloud)
      6. Plays emotive motion   (MotionPlayer, local servos)
    """

    def __init__(
        self,
        servo_controller=None,
        motion_player=None,
        personality_name: str = DEFAULT_PERSONALITY,
    ):
        # ── Personality ───────────────────────────────────────
        self.personalities = load_personalities()
        self._personality_name = personality_name
        self._personality = self.personalities.get(personality_name)
        if self._personality is None:
            print(f"[WARN] Personality '{personality_name}' not found, "
                  f"falling back to '{DEFAULT_PERSONALITY}'.")
            self._personality_name = DEFAULT_PERSONALITY
            self._personality = self.personalities[DEFAULT_PERSONALITY]

        # ── Conversation history (kept per session) ───────────
        self.conversation: list[dict] = []
        self._rebuild_system_message()

        # ── Hardware ──────────────────────────────────────────
        self.servo_controller = servo_controller
        self.motion_player = motion_player

        # ── Audio ─────────────────────────────────────────────
        pygame.mixer.init()
        self._pa = pyaudio.PyAudio()

        # ── openWakeWord (fully open source, no API key needed) ──
        # Auto-downloads the model from HuggingFace on first run.
        self._oww = OWWModel(wakeword_models=[WAKE_WORD])
        self._oww_threshold = 0.5  # tune up (fewer false positives) or down

        # Thread-safe personality switching (dashboard can call set_personality)
        self._lock = threading.Lock()

    # ── Personality management ─────────────────────────────────

    @property
    def personality_name(self) -> str:
        with self._lock:
            return self._personality_name

    def set_personality(self, name: str) -> bool:
        """Switch to a different personality. Returns True on success."""
        with self._lock:
            if name not in self.personalities:
                print(f"[WARN] Unknown personality: {name}")
                return False

            self._personality_name = name
            self._personality = self.personalities[name]
            self._rebuild_system_message()
            # Clear conversation so the new personality starts fresh
            self.conversation = [self.conversation[0]]
            print(f"[INFO] Personality changed to: {self._personality['display_name']}")
            return True

    def _rebuild_system_message(self):
        """(Re)set the system message from the active personality."""
        system_msg = {
            "role": "system",
            "content": self._personality["system_prompt"],
        }
        if self.conversation:
            self.conversation[0] = system_msg
        else:
            self.conversation = [system_msg]

    # ── 1. Wake word detection ─────────────────────────────────

    def listen_for_wake_word(self):
        """
        Block until the wake word is detected.
        Uses openWakeWord with 1280-sample (80ms) frames at 16kHz.
        No API key required — fully open source.
        """
        chunk = 1280  # 80ms at 16kHz — required by openWakeWord
        stream = self._pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=chunk,
        )

        # Reset model scores so stale detections don't carry over
        self._oww.reset()

        try:
            while True:
                pcm = stream.read(chunk, exception_on_overflow=False)
                audio_data = np.frombuffer(pcm, dtype=np.int16)

                prediction = self._oww.predict(audio_data)

                # Check all loaded wake word models
                for model_name, score in prediction.items():
                    if score > self._oww_threshold:
                        print(f"\n✦  Wake word detected! (score={score:.2f})")
                        return
        finally:
            stream.stop_stream()
            stream.close()

    # ── 2. Record user speech ──────────────────────────────────

    def record_speech(self) -> str | None:
        """
        Record from mic until silence is detected (or max time).
        Returns path to a temporary .wav file, or None if nothing was captured.
        """
        chunk_size = 1024
        stream = self._pa.open(
            rate=SAMPLE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=chunk_size,
        )

        print("🎙  Listening... (speak now)")
        frames: list[bytes] = []
        silent_chunks = 0
        max_chunks = int(SAMPLE_RATE / chunk_size * RECORD_SECONDS_MAX)
        silence_limit = int(SAMPLE_RATE / chunk_size * SILENCE_DURATION)

        # Wait for the user to start speaking (skip leading silence)
        started = False

        try:
            for _ in range(max_chunks):
                data = stream.read(chunk_size, exception_on_overflow=False)
                rms = self._rms(data)

                if not started:
                    if rms > SILENCE_THRESHOLD:
                        started = True
                        frames.append(data)
                    continue

                frames.append(data)

                if rms < SILENCE_THRESHOLD:
                    silent_chunks += 1
                    if silent_chunks >= silence_limit:
                        break
                else:
                    silent_chunks = 0

        finally:
            stream.stop_stream()
            stream.close()

        if not frames:
            print("[INFO] No speech detected.")
            return None

        # Write to WAV
        wav_path = TEMP_AUDIO_PATH
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self._pa.get_sample_size(pyaudio.paInt16))
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(b"".join(frames))

        duration = len(frames) * chunk_size / SAMPLE_RATE
        print(f"📝  Recorded {duration:.1f}s of audio.")
        return wav_path

    @staticmethod
    def _rms(data: bytes) -> float:
        """Compute root-mean-square energy of a 16-bit PCM chunk."""
        shorts = np.frombuffer(data, dtype=np.int16).astype(np.float64)
        if len(shorts) == 0:
            return 0.0
        return float(np.sqrt(np.mean(shorts ** 2)))

    # ── 3. Transcribe speech (Whisper API) ─────────────────────

    def transcribe(self, audio_path: str) -> str | None:
        """Send audio to OpenAI Whisper and return the transcript."""
        try:
            with open(audio_path, "rb") as f:
                result = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="en",
                )
            text = result.text.strip()
            if text:
                print(f"👤  You said: \"{text}\"")
            return text or None
        except Exception as exc:
            print(f"[ERROR] Whisper transcription failed: {exc}")
            return None

    # ── 4. Generate response (GPT-4o-mini) ─────────────────────

    def think(self, user_text: str) -> str:
        """Send conversation to GPT-4o-mini, return the assistant's reply."""
        self.conversation.append({"role": "user", "content": user_text})

        try:
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=self.conversation,
                max_tokens=200,
                temperature=0.8,
            )
            reply = response.choices[0].message.content.strip()
        except Exception as exc:
            print(f"[ERROR] GPT response failed: {exc}")
            reply = "Sorry, I couldn't think of a response right now."

        self.conversation.append({"role": "assistant", "content": reply})

        # Keep conversation from growing unbounded (last 20 exchanges)
        if len(self.conversation) > 41:  # 1 system + 40 user/assistant
            self.conversation = [self.conversation[0]] + self.conversation[-40:]

        print(f"🤖  {self._personality['display_name']}: {reply}")
        return reply

    # ── 5. Speak (ElevenLabs TTS) ──────────────────────────────

    def speak(self, text: str):
        """Convert text to emotive speech via ElevenLabs, then play it."""
        voice_cfg = self._personality.get("voice", {})
        voice_id = voice_cfg.get("voice_id", "EXAVITQu4vr4xnSDxMaL")
        model_id = voice_cfg.get("model_id", "eleven_multilingual_v2")
        settings = voice_cfg.get("settings", {})

        if elevenlabs_client is None:
            self._speak_fallback(text)
            return

        try:
            # Generate audio via ElevenLabs
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

            # Collect the streamed audio bytes
            audio_bytes = b"".join(audio_generator)

            # Play with pygame
            sound = pygame.mixer.Sound(io.BytesIO(audio_bytes))
            sound.play()

            # Wait for playback to finish
            while pygame.mixer.get_busy():
                time.sleep(0.1)

        except Exception as exc:
            print(f"[ERROR] ElevenLabs TTS failed: {exc}")
            self._speak_fallback(text)

    @staticmethod
    def _speak_fallback(text: str):
        """Fallback TTS using pyttsx3 if ElevenLabs is unavailable."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            print(f"[ERROR] Fallback TTS also failed: {exc}")
            print(f"[FALLBACK TEXT] {text}")

    # ── 6. Emote (servo motion) ────────────────────────────────

    def emote(self):
        """Play the emotive servo motion for the current personality."""
        if self.motion_player is None:
            return

        try:
            self.motion_player.play(self._personality_name)
        except Exception as exc:
            print(f"[ERROR] Motion playback failed: {exc}")

    # ── Main loop ──────────────────────────────────────────────

    def run(self):
        """
        Main assistant loop:
          wake word → record → transcribe → think → speak + emote (concurrent)
        Runs forever until interrupted with Ctrl+C.
        """
        print("━" * 50)
        print(f"  JARVIS is online.")
        print(f"  Personality: {self._personality['display_name']}")
        print(f"  Say \"{WAKE_WORD.title()}\" to begin.")
        print("━" * 50)

        try:
            while True:
                # 1. Wait for wake word
                self.listen_for_wake_word()

                # 2. Record user speech
                audio_path = self.record_speech()
                if audio_path is None:
                    print("[INFO] No audio captured, going back to sleep.\n")
                    continue

                # 3. Transcribe
                user_text = self.transcribe(audio_path)
                if user_text is None:
                    print("[INFO] Couldn't understand, going back to sleep.\n")
                    continue

                # 4. Think
                reply = self.think(user_text)

                # 5. Speak + Emote concurrently
                speak_thread = threading.Thread(target=self.speak, args=(reply,))
                emote_thread = threading.Thread(target=self.emote)

                speak_thread.start()
                emote_thread.start()

                speak_thread.join()
                emote_thread.join()

                print()  # visual separator between exchanges

        except KeyboardInterrupt:
            print("\n[INFO] Shutting down JARVIS...")
        finally:
            self.cleanup()

    # ── Cleanup ────────────────────────────────────────────────

    def cleanup(self):
        """Release all resources."""
        if hasattr(self, "_pa") and self._pa is not None:
            self._pa.terminate()
        pygame.mixer.quit()
        print("[INFO] Resources released. Goodbye.")
