# Eve — Personal AI Assistant with Speech

Eve is a command-line personal assistant. Basic commands are handled instantly
on your machine; everything else is answered by Claude with conversation
memory. Every reply is printed and spoken aloud.

## Features (the basics)

- **Greetings** — "hello", "hi", "good morning"
- **Time** — "what time is it"
- **Date** — "what's the date", "what day is it"
- **Help** — "help", "what can you do"
- **Chat** — anything else goes to Claude (remembers the conversation)
- **Speech** — replies are spoken aloud via offline TTS; falls back to
  text-only automatically if no audio is available

## Setup

```bash
pip install -r requirements.txt
```

Speech uses [pyttsx3](https://pypi.org/project/pyttsx3/), which is fully
offline. On Linux it needs espeak (`sudo apt install espeak-ng`); on macOS and
Windows it uses the built-in system voices.

For the AI chat, the Anthropic SDK needs credentials — either:

```bash
export ANTHROPIC_API_KEY=your-key-here
```

or sign in once with `ant auth login`. Without credentials, Eve still runs
with the basic commands.

## Run

```bash
python eve.py            # with speech
python eve.py --no-voice # text-only
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
