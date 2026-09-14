#!/usr/bin/env python3
"""Eve — a personal AI assistant with speech input and output.

Basic commands (time, date, greetings, help, exit) are handled locally.
Anything else is answered by Claude, with conversation memory.
You can talk to Eve through your microphone (SpeechRecognition) or type;
replies are spoken aloud with pyttsx3 when a TTS engine is available,
and always printed to the terminal.
"""

import argparse
import datetime
import sys

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import anthropic
except ImportError:
    anthropic = None

SYSTEM_PROMPT = (
    "You are Eve, a friendly personal assistant. Your replies are read aloud "
    "by a text-to-speech engine, so keep them short and conversational: one to "
    "three spoken sentences, no markdown, no lists, no code blocks."
)

EXIT_WORDS = {"exit", "quit", "bye", "goodbye"}
GREETING_WORDS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"}
TIME_PHRASES = {"time", "what time is it", "what's the time", "what is the time", "tell me the time"}
DATE_PHRASES = {"date", "what's the date", "what is the date", "what day is it", "today's date", "tell me the date"}

HELP_TEXT = (
    "I can tell you the time or the date, and chat about anything else. "
    "Say goodbye when you want to leave."
)


class Voice:
    """Speaks text aloud via pyttsx3; falls back to text-only if TTS is unavailable."""

    def __init__(self, enabled=True):
        self.engine = None
        if enabled and pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", 175)
            except Exception:
                self.engine = None
        if enabled and self.engine is None:
            print("(voice unavailable — running in text-only mode)")

    def say(self, text):
        print(f"Eve: {text}")
        if self.engine is not None:
            try:
                self.engine.say(text)
                self.engine.runAndWait()
            except Exception:
                self.engine = None
                print("(voice stopped working — continuing in text-only mode)")


class Ears:
    """Listens for speech on the microphone; unavailable if there's no mic."""

    def __init__(self, enabled=True):
        self.recognizer = None
        self.mic = None
        if enabled and sr is not None:
            try:
                self.recognizer = sr.Recognizer()
                self.mic = sr.Microphone()
                with self.mic as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            except Exception:
                self.mic = None
        if enabled and self.mic is None:
            print("(microphone unavailable — type your messages instead)")

    @property
    def available(self):
        return self.mic is not None

    def listen(self):
        """Return recognized speech, or None if nothing was understood."""
        print("(listening — speak now)")
        try:
            with self.mic as source:
                audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=15)
        except sr.WaitTimeoutError:
            return None
        except Exception:
            self.mic = None
            print("(microphone stopped working — type your messages instead)")
            return None
        try:
            text = self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            print("(sorry, I didn't catch that)")
            return None
        except sr.RequestError:
            print("(speech recognition needs internet — type your message instead)")
            return None
        print(f"You: {text}")
        return text


class ClaudeBrain:
    """Multi-turn conversation with Claude for anything the built-ins don't cover."""

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.messages = []

    def reply(self, user_text):
        self.messages.append({"role": "user", "content": user_text})
        try:
            response = self.client.messages.create(
                model="claude-opus-5",
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                messages=self.messages,
            )
        except TypeError:
            # The SDK raises TypeError at request time when no credentials
            # (API key, auth token, or profile) could be resolved.
            self.messages.pop()
            return (
                "I don't have Anthropic credentials, so I can only do basic "
                "commands. Set ANTHROPIC_API_KEY to unlock chat."
            )
        except anthropic.AuthenticationError:
            self.messages.pop()
            return "I couldn't sign in to my brain. Please check your Anthropic API key."
        except anthropic.RateLimitError:
            self.messages.pop()
            return "I'm being rate limited. Give me a moment and ask again."
        except anthropic.APIStatusError as e:
            self.messages.pop()
            return f"My brain returned an error ({e.status_code}). Try again in a bit."
        except anthropic.APIConnectionError:
            self.messages.pop()
            return "I can't reach the internet right now, so I can only do my basic commands."

        text = next((b.text for b in response.content if b.type == "text"), "")
        if not text:
            self.messages.pop()
            return "Sorry, I came up blank on that one."
        self.messages.append({"role": "assistant", "content": text})
        return text


def builtin_reply(user_text):
    """Return a reply for basic commands, or None if Claude should handle it."""
    t = user_text.lower().strip().rstrip("?!.")
    if t in EXIT_WORDS:
        return "exit"
    if t in GREETING_WORDS:
        return "Hello! I'm Eve, your personal assistant. How can I help?"
    if t in ("help", "what can you do"):
        return HELP_TEXT
    if t in TIME_PHRASES:
        return f"It's {datetime.datetime.now().strftime('%I:%M %p').lstrip('0')}."
    if t in DATE_PHRASES:
        return f"Today is {datetime.datetime.now().strftime('%A, %B %d, %Y')}."
    return None


def main():
    parser = argparse.ArgumentParser(description="Eve — a personal AI assistant with speech.")
    parser.add_argument("--no-voice", action="store_true", help="disable speech output")
    parser.add_argument("--no-mic", action="store_true", help="disable voice input (type instead)")
    args = parser.parse_args()

    voice = Voice(enabled=not args.no_voice)
    ears = Ears(enabled=not args.no_mic)
    brain = ClaudeBrain() if anthropic is not None else None
    if brain is None:
        print("(anthropic package not installed — only basic commands will work)")

    voice.say("Hi, I'm Eve. Ask me anything, or say help to hear what I can do.")

    while True:
        try:
            if ears.available:
                user_text = ears.listen()
                if user_text is None:
                    continue
                user_text = user_text.strip()
            else:
                user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            voice.say("Goodbye!")
            break
        if not user_text:
            continue

        reply = builtin_reply(user_text)
        if reply == "exit":
            voice.say("Goodbye! Talk to you soon.")
            break
        if reply is None:
            if brain is not None:
                reply = brain.reply(user_text)
            else:
                reply = "I can only do basic commands right now. Say help to hear them."
        voice.say(reply)


if __name__ == "__main__":
    main()
