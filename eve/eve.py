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
import pathlib
import queue
import re
import sys
import threading
import time

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
    "I can tell you the time or the date, set reminders — like, remind me to "
    "stretch in 20 minutes — queue up bigger jobs — like, queue a task: plan "
    "my week — and chat about anything else. "
    "Say goodbye when you want to leave."
)


class Voice:
    """Speaks text aloud via pyttsx3; falls back to text-only if TTS is unavailable."""

    def __init__(self, enabled=True):
        self.engine = None
        self._lock = threading.Lock()  # reminders speak from a background thread
        reason = "the pyttsx3 package is not installed — run: pip install pyttsx3"
        if enabled and pyttsx3 is not None:
            try:
                self.engine = pyttsx3.init()
                self.engine.setProperty("rate", 175)
            except Exception as e:
                self.engine = None
                reason = f"{e.__class__.__name__}: {e}"
        if enabled and self.engine is None:
            print(f"(voice unavailable, running in text-only mode — {reason})")

    def say(self, text):
        with self._lock:
            print(f"Eve: {text}")
            if self.engine is not None:
                try:
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception:
                    self.engine = None
                    print("(voice stopped working — continuing in text-only mode)")


class Reminders:
    """Holds pending reminders and announces them when due (while Eve runs)."""

    def __init__(self, voice):
        self.voice = voice
        self.items = []  # list of (due: datetime, task: str)
        self.lock = threading.Lock()
        threading.Thread(target=self._watch, daemon=True).start()

    def add(self, due, task):
        with self.lock:
            self.items.append((due, task))

    def list_text(self):
        with self.lock:
            if not self.items:
                return "You have no reminders."
            parts = [
                f"{task} at {due.strftime('%I:%M %p').lstrip('0')}"
                for due, task in sorted(self.items)
            ]
        return "You have " + ("one reminder: " if len(parts) == 1 else f"{len(parts)} reminders: ") + "; ".join(parts) + "."

    def _watch(self):
        while True:
            now = datetime.datetime.now()
            with self.lock:
                due_now = [task for due, task in self.items if due <= now]
                self.items = [(due, task) for due, task in self.items if due > now]
            for task in due_now:
                self.voice.say(f"Reminder: {task}!")
            time.sleep(1)


IN_PATTERN = re.compile(
    r"remind me (?:to |about |that )?(.+?) in (\d+) (second|minute|hour)s?$"
)
IN_FIRST_PATTERN = re.compile(
    r"remind me in (\d+) (second|minute|hour)s? (?:to |about |that )?(.+)$"
)
AT_PATTERN = re.compile(
    r"remind me (?:to |about |that )?(.+?) at (\d{1,2})(?::(\d{2}))?\s*(am|pm)?$"
)
LIST_PHRASES = {
    "list reminders", "list my reminders", "my reminders",
    "what are my reminders", "show my reminders", "do i have any reminders",
}


def reminder_reply(user_text, reminders):
    """Handle reminder commands; return a reply, or None if not a reminder."""
    t = user_text.lower().strip().rstrip("?!.")
    if t in LIST_PHRASES:
        return reminders.list_text()

    match = IN_PATTERN.fullmatch(t) or IN_FIRST_PATTERN.fullmatch(t)
    if match:
        if match.re is IN_FIRST_PATTERN:
            amount, unit, task = match.groups()
        else:
            task, amount, unit = match.groups()
        seconds = int(amount) * {"second": 1, "minute": 60, "hour": 3600}[unit]
        due = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        reminders.add(due, task)
        return f"Okay, I'll remind you: {task}, in {amount} {unit}{'s' if int(amount) != 1 else ''}."

    match = AT_PATTERN.fullmatch(t)
    if match:
        task, hour, minute, ampm = match.groups()
        hour, minute = int(hour), int(minute or 0)
        if hour > 23 or minute > 59:
            return "I didn't understand that time. Try something like: remind me to call mom at 5:30 pm."
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        now = datetime.datetime.now()
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if due <= now:
            due += datetime.timedelta(days=1)
        reminders.add(due, task)
        day = "tomorrow" if due.date() != now.date() else "today"
        return f"Okay, I'll remind you: {task}, at {due.strftime('%I:%M %p').lstrip('0')} {day}."

    if t.startswith("remind me"):
        return (
            "I can set a reminder if you tell me when. Try: remind me to stretch "
            "in 20 minutes, or remind me to call mom at 5:30 pm."
        )
    return None


TASK_SYSTEM_PROMPT = (
    "You are Eve, a personal assistant, completing a background task for your "
    "user. Produce the complete, finished result of the task. The result is "
    "saved to a file, so markdown formatting is fine."
)


class Tasks:
    """Background task queue: Claude works through tasks while you keep chatting."""

    def __init__(self, voice, outdir="eve_tasks"):
        self.voice = voice
        self.client = anthropic.Anthropic() if anthropic is not None else None
        self.outdir = pathlib.Path(outdir)
        self.queue = queue.Queue()
        self.items = []  # dicts: num, desc, status, path
        self.lock = threading.Lock()
        threading.Thread(target=self._work, daemon=True).start()

    def add(self, desc):
        with self.lock:
            item = {"num": len(self.items) + 1, "desc": desc, "status": "queued", "path": None}
            self.items.append(item)
        self.queue.put(item)
        return item["num"]

    def list_text(self):
        with self.lock:
            if not self.items:
                return "The task queue is empty."
            parts = []
            for item in self.items:
                status = item["status"]
                if status == "done":
                    status = f"done, saved to {item['path']}"
                parts.append(f"Task {item['num']}, {item['desc']}: {status}")
        return ". ".join(parts) + "."

    def _work(self):
        while True:
            item = self.queue.get()
            with self.lock:
                item["status"] = "working"
            error = None
            try:
                response = self.client.messages.create(
                    model="claude-opus-5",
                    max_tokens=16000,
                    system=TASK_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": item["desc"]}],
                )
                text = next((b.text for b in response.content if b.type == "text"), "")
                if not text:
                    error = "Claude returned an empty result"
            except TypeError:
                error = "no Anthropic credentials — set ANTHROPIC_API_KEY"
            except anthropic.APIConnectionError:
                error = "couldn't reach the internet"
            except anthropic.APIError as e:
                error = f"API error: {getattr(e, 'message', None) or e}"

            if error is not None:
                with self.lock:
                    item["status"] = f"failed ({error})"
                self.voice.say(f"Task {item['num']} failed: {error}.")
                continue
            self.outdir.mkdir(exist_ok=True)
            path = self.outdir / f"task-{item['num']}.md"
            path.write_text(f"# Task {item['num']}: {item['desc']}\n\n{text}\n")
            with self.lock:
                item["status"] = "done"
                item["path"] = str(path)
            self.voice.say(f"Task {item['num']} is done: {item['desc']}. I saved the result to {path}.")


TASK_ADD_PATTERN = re.compile(r"(?:queue|add|new)(?: a| another| up a)? task[:,]?\s*(.+)$")
TASK_LIST_PHRASES = {
    "list tasks", "list my tasks", "my tasks", "what are my tasks",
    "show my tasks", "task status", "how are my tasks", "how are my tasks going",
}


def task_reply(user_text, tasks):
    """Handle task-queue commands; return a reply, or None if not a task command."""
    t = user_text.lower().strip().rstrip("?!.")
    if t in TASK_LIST_PHRASES:
        return tasks.list_text() if tasks is not None else "The task queue is empty."
    match = TASK_ADD_PATTERN.fullmatch(t)
    if match:
        if tasks is None:
            return "I need the anthropic package installed to work on tasks."
        num = tasks.add(match.group(1))
        return f"Task {num} queued: {match.group(1)}. I'll let you know when it's done."
    if t in ("queue a task", "add a task", "new task", "add another task"):
        return "Sure — what's the task? Say something like: queue a task: plan my week."
    return None


class Ears:
    """Listens for speech on the microphone; unavailable if there's no mic."""

    def __init__(self, enabled=True):
        self.recognizer = None
        self.mic = None
        reason = "the SpeechRecognition package is not installed — run: pip install SpeechRecognition PyAudio"
        if enabled and sr is not None:
            try:
                self.recognizer = sr.Recognizer()
                self.mic = sr.Microphone()
                with self.mic as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            except Exception as e:
                self.mic = None
                reason = f"{e.__class__.__name__}: {e}"
        if enabled and self.mic is None:
            print(f"(microphone unavailable, type your messages instead — {reason})")

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
    reminders = Reminders(voice)
    tasks = Tasks(voice) if anthropic is not None else None
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
            reply = reminder_reply(user_text, reminders)
        if reply is None:
            reply = task_reply(user_text, tasks)
        if reply is None:
            if brain is not None:
                reply = brain.reply(user_text)
            else:
                reply = "I can only do basic commands right now. Say help to hear them."
        voice.say(reply)


if __name__ == "__main__":
    main()
