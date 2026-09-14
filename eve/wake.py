#!/usr/bin/env python3
"""Wake-word listener for Eve.

Runs in the background listening for "Hey Eve" on the microphone. When it
hears the wake phrase it launches eve.py, waits until you say goodbye to
Eve, then goes back to listening for the wake phrase. Ctrl-C quits.
"""

import pathlib
import subprocess
import sys

try:
    import speech_recognition as sr
except ImportError:
    sr = None

WAKE_TOKENS = {"eve", "eva"}  # "eva" is a common mis-hearing of "Eve"
EVE_SCRIPT = pathlib.Path(__file__).with_name("eve.py")


def main():
    if sr is None:
        print("SpeechRecognition is not installed — run: pip install -r requirements.txt")
        return 1
    recognizer = sr.Recognizer()
    try:
        mic = sr.Microphone()
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
    except Exception:
        print("No microphone available — start Eve directly with: python eve.py")
        return 1

    print("Listening for 'Hey Eve'... (Ctrl-C to quit)")
    while True:
        try:
            with mic as source:
                audio = recognizer.listen(source, phrase_time_limit=4)
            heard = recognizer.recognize_google(audio).lower()
        except KeyboardInterrupt:
            print("\nBye.")
            return 0
        except Exception:
            continue  # silence, unintelligible speech, or a network hiccup
        if WAKE_TOKENS & set(heard.split()):
            print(f"(heard: {heard}) — starting Eve.")
            subprocess.run([sys.executable, str(EVE_SCRIPT)])
            print("Eve exited. Listening for 'Hey Eve' again... (Ctrl-C to quit)")


if __name__ == "__main__":
    sys.exit(main())
