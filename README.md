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

## 🚀 Installation

1. **Download the Code:**
   Click the green **Code** button at the top of this page and select **Download ZIP**. Extract the folder to your computer.

2. **Run the Installer:**
   Right-click the **`install.ps1`** file and select **Run with PowerShell**. 
   *Note: This script will automatically install Python and FFmpeg if you don't have them, create a virtual environment, and download all the AI models. It may take 10-20 minutes.*

3. **Pocket TTS Voice Cloning Setup (One-time step):**
   *   Create a free account at [huggingface.co](https://huggingface.co).
   *   Accept the terms on the [Pocket TTS Model Page](https://huggingface.co/kyutai/pocket-tts).
   *   Create a Read Token at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).
   *   Log in locally by running this command in PowerShell inside the folder: 
       `.\.venv\Scripts\hf.exe auth login`

## 🎮 How to Use
1. Right-click **`start.ps1`** and select **Run with PowerShell**.
2. Your browser will open to `http://localhost:8501`.
3. Upload the chapter's `.mp3` and the book's `.txt` file.
4. Click **Start Transcription** (takes ~15-25 mins on CPU).
5. Review the gap, edit the text, set the cut point, and generate the voice.
6. Click **Generate Spliced Version**.

## ✍️ The Text Preparation Guide
AI Text-to-Speech models are trained on modern English. When fed 19th-century literature, they often stumble. Before generating, you should act as the editor:
*   **Remove Smart Quotes:** Delete `“ ”`, `( )`, and `[ ]`. Replace them with commas.
*   **Fix the Dashes:** Replace em-dashes (`—`) and double hyphens (`--`) with periods so the AI takes a breath.
*   **Experiment with Phonetic Spelling:** If the AI mispronounces a foreign word or name, you can try spelling it phonetically using spaces or periods (avoid hyphens, as the AI reads them as literal pauses). 
*   **Watch Semicolons:** Replace semicolons with periods to prevent the AI from rushing through a massive sentence.

## ⚖️ Legal & Ethical Considerations

This tool was assembled by stringing together existing open-source tools, with AI assistance, exclusively for audiobooks in the public domain. 

*   **Public Domain Audio:** Public domain audio can be freely reproduced, modified, and redistributed, though status can vary by country. 
*   **Voice Cloning Law:** Voice cloning law is less settled. In the US, liability runs through state right-of-publicity statutes, with Tennessee’s ELVIS Act the strictest example. In the EU, the AI Act requires disclosure of synthetic audio from August 2026, regardless of consent. In the UK, there’s currently no standalone personality or voice right, though reform is being discussed. 
*   **Scope of this Tool:** For this specific tool, narrators are anonymous volunteers rather than commercial talent, and the tool only reconstructs missing passages using that same narrator’s own sampled voice. It doesn’t generate new content in their likeness, runs entirely local with no cloud processing, and doesn’t distribute the voice model commercially.

## 📄 License
This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. See the `LICENSE` file for details.
