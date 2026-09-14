# Eve — Personal AI Assistant with Speech

Eve is a command-line personal assistant you can talk to. Basic commands are
handled instantly on your machine; everything else is answered by Claude with
conversation memory. Every reply is printed and spoken aloud.

## Features (the basics)

- **Greetings** — "hello", "hi", "good morning"
- **Time** — "what time is it"
- **Date** — "what's the date", "what day is it"
- **Reminders** — "remind me to stretch in 20 minutes", "remind me to call
  mom at 5:30 pm", "list my reminders"; Eve announces them out loud when
  they're due (while she's running — they aren't saved between sessions)
- **Help** — "help", "what can you do"
- **Chat** — anything else goes to Claude (remembers the conversation)
- **Voice input** — talk to Eve through your microphone; falls back to
  typed input automatically if no mic is available
- **Speech** — replies are spoken aloud via offline TTS; falls back to
  text-only automatically if no audio is available

## Setup

```bash
pip install -r requirements.txt
```

Speech output uses [pyttsx3](https://pypi.org/project/pyttsx3/), which is
fully offline. On Linux it needs espeak (`sudo apt install espeak-ng`); on
macOS and Windows it uses the built-in system voices.

Voice input uses
[SpeechRecognition](https://pypi.org/project/SpeechRecognition/) with PyAudio
for microphone access, and the free Google Web Speech API for recognition (so
it needs internet). PyAudio needs PortAudio on Linux
(`sudo apt install portaudio19-dev`) and Homebrew's `portaudio` on macOS.
Without a microphone, Eve falls back to typed input.

For the AI chat, the Anthropic SDK needs credentials — either:

```bash
export ANTHROPIC_API_KEY=your-key-here
```

or sign in once with `ant auth login`. Without credentials, Eve still runs
with the basic commands.

## Run

```bash
python eve.py            # talk to Eve, she talks back
python eve.py --no-mic   # type instead of talking
python eve.py --no-voice # silent replies (text only)
```

Say `bye`, `exit`, or `quit` (or press Ctrl-C) to leave.

## Example

```
Eve: Hi, I'm Eve. Ask me anything, or say help to hear what I can do.
You: hello
Eve: Hello! I'm Eve, your personal assistant. How can I help?
You: what time is it
Eve: It's 3:42 PM.
You: what's a good dinner I can cook in 20 minutes?
Eve: A garlic butter pasta with spinach and parmesan is hard to beat...
You: bye
Eve: Goodbye! Talk to you soon.
```
