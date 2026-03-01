# GetMeOut
HackHer 2026 Project!!

# ABOUT
Get Me Out listens continuously to your microphone using Vosk, a lightweight offline speech recognition engine, transcribing audio locally so nothing ever leaves your device. When it detects one of your custom trigger keywords in the transcript, it waits a configurable delay long enough to feel natural and then hijacks your screen with a fake incoming call overlay. The decoy caller screen mimics a real facetime call with a caller ID, and a live call timer once "accepted," and can play back a pre-recorded audio file through the call to make it even more convincing. Everything runs on a background thread so the UI stays responsive, and if Vosk or PyAudio aren't available it falls back to a demo mode automatically.
