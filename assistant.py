# assistant.py — JARVIS with Google integrations (email, calendar, timers)

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import wave

import numpy as np
import pyaudio
import subprocess

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
    AUDIO_OUTPUT_DEVICE,
)

load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

try:
    from elevenlabs import ElevenLabs
    elevenlabs_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
except Exception:
    elevenlabs_client = None
    print("[WARN] ElevenLabs not available")

# ─── Intent parsing system prompt ───────────────────────────────────────────
_INTENT_SYSTEM_PROMPT = """
You are JARVIS, an AI assistant. Analyze the user's request and return ONLY valid JSON
in exactly this schema — no markdown, no extra keys:

{
  "emotion": "<one of: happy_excited | angry | scared | sad_tired | disgusted | rizz>",
  "response": "<spoken reply to the user>",
  "action": "<one of: none | send_email | create_calendar_event | set_timer | cancel_timer | list_timers | list_today_events>",
  "action_args": {}
}

Rules for action_args by action:

send_email:
  { "to": "<email>", "subject": "<subject>", "body": "<plain text body>", "cc": "<optional>", "bcc": "<optional>" }

create_calendar_event:
  { "summary": "<title>", "start_iso": "<ISO-8601 datetime>", "end_iso": "<ISO-8601 datetime>", "description": "<optional>", "location": "<optional>" }
  Use today's date if the user doesn't specify. Default duration 1 hour.

set_timer:
  { "label": "<descriptive name>", "seconds": <integer> }
  Convert minutes/hours to seconds. Default label: "timer".

cancel_timer:
  { "label": "<timer name to cancel>" }

list_timers:
  {}

list_today_events:
  {}

If no action is needed, use "action": "none" and "action_args": {}.
Today's date/time context will be injected into each user message.
"""


def load_personalities(path: str = "personality.json") -> dict:
    with open(path, "r") as f:
        return json.load(f)["personality_profiles"]


class VoiceAssistant:

    def __init__(self, motion_player=None, google_actions=None):
        self.personalities = load_personalities()
        self._personality_name = DEFAULT_PERSONALITY
        self._personality = self.personalities[self._personality_name]

        self._pa = pyaudio.PyAudio()
        self.listening_enabled = True
        self.motion_player = motion_player
        self.google_actions = google_actions

        self.is_speaking = False

    # ─────────────────────── Personality ────

    @property
    def personality_name(self) -> str:
        return self._personality_name

    def set_personality(self, name: str) -> None:
        if name in self.personalities:
            if name != self._personality_name:
                print(f"[INFO] Switching personality → {name}")
            self._personality_name = name
            self._personality = self.personalities[name]

    def set_listening(self, enabled: bool) -> None:
        self.listening_enabled = enabled
        print(f"[INFO] Listening {'ON' if enabled else 'OFF'}")

    # ─────────────────────── Audio playback ────

    def _play_audio_blocking(self, filepath: str) -> None:
        subprocess.run(["aplay", "-D", AUDIO_OUTPUT_DEVICE, filepath])

    def _generate_audio(self, text: str) -> str | None:
        if elevenlabs_client is None:
            return None

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
            stderr=subprocess.DEVNULL,
        )

        return wav_path

    # ─────────────────────── Recording ────

    def record(self) -> str:
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
            rms = float(np.sqrt(np.mean(samples ** 2)))
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

    # ─────────────────────── Transcription ────

    def transcribe(self, path: str) -> str | None:
        try:
            with open(path, "rb") as f:
                result = openai_client.audio.transcriptions.create(
                    model="whisper-1", file=f
                )
            text = result.text.strip()
            print(f"👤 {text}")
            return text
        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}")
            return None

    # ─────────────────────── Thinking / Intent ────

    def think(self, text: str):
        """
        Send user text to GPT with intent detection.
        Returns (emotion, reply, action, action_args).
        """
        import datetime as dt
        now_str = dt.datetime.now().strftime("%A, %B %d, %Y %I:%M %p")

        user_message = f"[Current time: {now_str}]\nUser: {text}"

        try:
            response = openai_client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
            )
            raw = response.choices[0].message.content.strip()

            # Strip markdown code fences if GPT wraps it anyway
            raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("` \n")

            data = json.loads(raw)
            emotion = data.get("emotion", DEFAULT_PERSONALITY)
            reply = data.get("response", "I'm not sure what to do with that.")
            action = data.get("action", "none")
            action_args = data.get("action_args", {})

            print(f"🤖 [{emotion}] {reply}")
            if action != "none":
                print(f"   ↳ action={action} args={action_args}")

            return emotion, reply, action, action_args

        except Exception as e:
            print(f"[ERROR] GPT failed: {e}")
            return DEFAULT_PERSONALITY, "I encountered an error.", "none", {}

    # ─────────────────────── Action dispatch ────

    def _dispatch_action(self, action: str, action_args: dict) -> str | None:
        """
        Execute a Google action and return a short status string
        that can be appended to JARVIS's spoken reply.
        """
        if not self.google_actions:
            return "Google integrations aren't connected right now."

        ga = self.google_actions

        try:
            if action == "send_email":
                result = ga.send_email(
                    to=action_args["to"],
                    subject=action_args.get("subject", "(no subject)"),
                    body_text=action_args.get("body", ""),
                    cc=action_args.get("cc"),
                    bcc=action_args.get("bcc"),
                )
                return f"Email sent! Message ID: {result['id']}"

            elif action == "create_calendar_event":
                result = ga.create_calendar_event(
                    summary=action_args["summary"],
                    start_iso=action_args["start_iso"],
                    end_iso=action_args["end_iso"],
                    description=action_args.get("description", ""),
                    location=action_args.get("location", ""),
                )
                return f"Event '{result['summary']}' created! Link: {result['htmlLink']}"

            elif action == "set_timer":
                label = action_args.get("label", "timer")
                seconds = float(action_args.get("seconds", 60))

                def _timer_fired(lbl: str):
                    """Called when the timer fires — speak an alert."""
                    alert = f"Hey! Your {lbl} is done!"
                    print(f"⏰ {alert}")
                    audio_path = self._generate_audio(alert)
                    if audio_path:
                        self._play_audio_blocking(audio_path)

                msg = ga.set_timer(label=label, seconds=seconds, on_fire=_timer_fired)
                return msg

            elif action == "cancel_timer":
                label = action_args.get("label", "timer")
                return ga.cancel_timer(label)

            elif action == "list_timers":
                active = ga.list_timers()
                if active:
                    return "Active timers: " + ", ".join(active) + "."
                return "No active timers."

            elif action == "list_today_events":
                events = ga.list_today_events()
                if not events:
                    return "Your calendar is clear today."
                lines = [f"{e['start']}: {e['summary']}" for e in events]
                return "Today's events: " + "; ".join(lines) + "."

        except KeyError as e:
            return f"I'm missing a required field for that action: {e}."
        except Exception as e:
            print(f"[ERROR] Action dispatch failed: {e}")
            return f"Something went wrong while executing the action: {e}"

        return None

    # ─────────────────────── Main loop ────

    def run(self) -> None:
        print("🚀 JARVIS ONLINE")

        try:
            while True:
                if self.is_speaking:
                    print("[DEBUG] Waiting for speech to finish...")
                    time.sleep(0.2)
                    continue

                if not self.listening_enabled:
                    print("[DEBUG] Listening OFF")
                    time.sleep(0.5)
                    continue

                audio = self.record()
                text = self.transcribe(audio)

                if not text:
                    continue

                if "jarvis" not in text.lower():
                    print("[DEBUG] No 'jarvis'")
                    continue

                print("🟢 Jarvis detected!")
                clean_text = text.lower().replace("jarvis", "").strip()

                emotion, reply, action, action_args = self.think(clean_text)
                self.set_personality(emotion)

                # Execute Google action (synchronously before speaking)
                action_status = None
                if action != "none":
                    action_status = self._dispatch_action(action, action_args)
                    if action_status:
                        print(f"[ACTION] {action_status}")
                        # Append status to spoken reply so JARVIS confirms out loud
                        reply = f"{reply} {action_status}"

                audio_path = self._generate_audio(reply)

                threads = []
                self.is_speaking = True

                if self.motion_player:
                    t_motion = threading.Thread(
                        target=self.motion_player.play, args=(emotion,)
                    )
                    threads.append(t_motion)
                    t_motion.start()

                if audio_path:
                    t_audio = threading.Thread(
                        target=self._play_audio_blocking, args=(audio_path,)
                    )
                    threads.append(t_audio)
                    t_audio.start()

                for t in threads:
                    t.join()

                self.is_speaking = False

                if self.motion_player:
                    time.sleep(0.1)
                    self.motion_player.play("neutral")

        except KeyboardInterrupt:
            print("\n[INFO] Shutting down...")

        finally:
            self._pa.terminate()