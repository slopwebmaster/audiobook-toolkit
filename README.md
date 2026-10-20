# 🎧 Audiobook Toolkit (Alpha)

A local, CPU-only toolkit for public domain audiobooks. It can scan audio against an ebook to flag missing text (Quality Control), clone the narrator's voice to patch skipped passages, and remaster the final audio to remove background noise.

No GPU required. No API keys. 100% free and private.

## ✨ Features
*   **Quality Control (QC):** Scans the audiobook against the ebook text to instantly flag every skipped sentence, misread word, or extra paragraph. Great for narrators who want to proofread their raw recordings.
*   **Patching:** Uses Kyutai's Pocket TTS to clone the narrator's voice from a short sample and generate the missing audio.
*   **Precision Splicing:** Built-in GUI to manually select the exact cut point. It applies mathematical fades to ensure the splice is seamless.
*   **AI Remastering (Optional):** Run the final patched file through DeepFilterNet to remove background hiss and metallic artifacts.

## 🛠️ Built With
*   **Transcription:** [OpenAI Whisper](https://github.com/openai/whisper) (via [Stable-ts](https://github.com/jianfch/stable-ts) for precise word-level timestamps).
*   **Text Alignment:** Python `difflib` (built-in).
*   **Voice Cloning:** [Kyutai Pocket TTS](https://github.com/kyutai-labs/pocket-tts).
*   **Audio Splicing:** [Pydub](https://github.com/jiaaro/pydub) & FFmpeg.
*   **Audio Remastering:** [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet).
*   **GUI:** [Streamlit](https://github.com/streamlit/streamlit).

## 💻 Requirements
*   **OS:** Windows 10/11
*   **RAM:** 16 GB recommended (The AI models require ~3 GB of RAM to load)
*   **CPU:** Any modern multi-core processor. *(No GPU required)*
*   **Software:** Python 3.12+, FFmpeg

## 🚀 Installation

1. **Install Python and FFmpeg:**
   Open PowerShell as Administrator and run:
   ```powershell
   winget install --id Python.Python.3.12 -e
   winget install --id Gyan.FFmpeg -e
