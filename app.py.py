import re
import json
import os
import time
import sys
from pathlib import Path
import numpy as np
import streamlit as st
import stable_whisper
import difflib
from pydub import AudioSegment
import subprocess

# ==========================================
# BACKEND LOGIC
# ==========================================

WORK_DIR   = Path(__file__).parent / "work"
OUTPUT_DIR = Path(__file__).parent / "output"
WORK_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def format_time(seconds):
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m:02d}:{s:06.3f}"

def roman_to_int(s):
    vals = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
    total = 0; prev = 0
    for ch in reversed(s.upper()):
        v = vals.get(ch, 0)
        total = total - v if v < prev else total + v
        prev = v
    return total

def split_chapters(full_text):
    pattern = re.compile(r"(?m)^\s*CHAPTER\s+([IVXLC]+)\s*\.?\s*$")
    by_num = {}
    for m in pattern.finditer(full_text):
        by_num[roman_to_int(m.group(1))] = m
    real = sorted(by_num.values(), key=lambda m: m.start())
    chapters = {}
    for i, m in enumerate(real):
        num = roman_to_int(m.group(1))
        start = m.end()
        end = real[i+1].start() if i + 1 < len(real) else len(full_text)
        chapters[num] = full_text[start:end]
    return chapters

def split_sentences(text):
    parts = re.split(r'(?<=[.!?"])\s+(?=[A-Z"])', text)
    return [p.strip() for p in parts if len(p.strip()) > 30]

def normalise(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

@st.cache_resource(show_spinner=False)
def load_model(model_name):
    return stable_whisper.load_model(model_name, device="cpu")

def transcribe_and_align(audio_path, chapter_num, model_name):
    cache_file = WORK_DIR / f"chapter{chapter_num:02d}_transcript.json"
    
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if data.get("segments") and "words" in data["segments"][0]:
                return data["segments"]
        
    model = load_model(model_name)
    result = model.transcribe(str(audio_path), language="en", word_timestamps=True)
    
    segs = []
    for s in result.segments:
        text = s.text.strip()
        if len(normalise(text)) < 10: continue
        
        words_data = []
        if hasattr(s, "words") and s.words:
            for w in s.words:
                words_data.append({
                    "text": w.word, "norm": normalise(w.word),
                    "start": w.start, "end": w.end
                })
                
        segs.append({
            "start": s.start, "end": s.end,
            "text": text, "words": words_data
        })
        
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"segments": segs}, f)
        
    return segs

def detect_gaps(segments, book_sentences, min_gap_words):
    book_text = " ".join(book_sentences)
    orig_words = book_text.split()
    
    flat_trans = []
    for seg in segments:
        flat_trans.extend(seg.get("words", []))
        
    orig_filtered = [w for w in orig_words if normalise(w)]
    trans_filtered = [w for w in flat_trans if w["norm"]]
    
    orig_norms = [normalise(w) for w in orig_filtered]
    trans_norms = [w["norm"] for w in trans_filtered]
    
    sm = difflib.SequenceMatcher(None, orig_norms, trans_norms)
    gaps = []
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ('delete', 'replace') and (i2 - i1) >= min_gap_words:
            
            if j1 == 0:
                gap_start_time = 0.0
            else:
                gap_start_time = trans_filtered[j1 - 1]["end"]
            
            if j1 >= len(trans_filtered):
                gap_end_time = trans_filtered[-1]["end"] + 2.0
            else:
                gap_end_time = trans_filtered[j1]["start"]

            missing_text = " ".join(orig_filtered[i1:i2])
            missing_text = re.sub(r'([.!?,;:])([a-zA-Z])', r'\1 \2', missing_text)
            
            before_ctx = " ".join(orig_filtered[max(0, i1-35):i1])
            after_ctx = " ".join(orig_filtered[i2:min(len(orig_filtered), i2+35)])
            
            gaps.append({
                "missing_text": missing_text,
                "before_book": "..." + before_ctx,
                "after_book": after_ctx + "...",
                "audio_start": gap_start_time,
                "audio_end": gap_end_time,
                "generated_path": None,
                "ref_path": None
            })
            
    return gaps

def extract_reference(audio_path, gap_start_sec, ref_seconds, ref_shift_sec=0):
    audio = AudioSegment.from_file(str(audio_path))
    end_sec = max(0, gap_start_sec - ref_shift_sec)
    end_ms = int(end_sec * 1000)
    start_ms = max(0, end_ms - ref_seconds * 1000)
    
    ref = audio[start_ms:end_ms]
    ref = ref.fade_out(100) 
    
    out = WORK_DIR / f"narrator_ref_{int(time.time())}.wav"
    ref.export(str(out), format="wav")
    return out

@st.cache_resource(show_spinner=False)
def load_tts():
    from pocket_tts import TTSModel
    return TTSModel.load_model()

def generate_clip(text, ref_wav, out_wav):
    import scipy.io.wavfile
    tts = load_tts()
    voice_state = tts.get_state_for_audio_prompt(str(ref_wav))
    
    clean_text = text.replace('“', '').replace('”', '').replace('"', '')
    clean_text = clean_text.replace('(', '').replace(')', '')
    clean_text = clean_text.replace('[', '').replace(']', '')
    clean_text = clean_text.replace('—', ' ').replace('-', ' ')
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    tts_text = f". {clean_text}"
    
    audio = tts.generate_audio(voice_state, tts_text)
    
    if hasattr(audio, "detach"): audio = audio.detach().cpu().numpy()
    elif hasattr(audio, "numpy"): audio = audio.numpy()
    audio = np.asarray(audio, dtype=np.float32).squeeze()
    sr = int(getattr(tts, "sample_rate", 24000))
    
    audio = audio - np.mean(audio)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > 0: audio = audio / peak * 0.89
    
    fade_samples = int(sr * 0.02)
    if len(audio) > fade_samples * 2:
        audio[:fade_samples] *= np.linspace(0, 1, fade_samples)
        audio[-fade_samples:] *= np.linspace(1, 0, fade_samples)
    
    audio_int16 = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
    scipy.io.wavfile.write(str(out_wav), sr, audio_int16)
    
    try:
        gen = AudioSegment.from_wav(str(out_wav)); ref = AudioSegment.from_wav(str(ref_wav))
        gain = ref.dBFS - gen.dBFS
        if abs(gain) > 0.5: (gen + gain).export(str(out_wav), format="wav")
    except Exception: pass
    return out_wav

def rebuild_audio(original_path, gaps, pause_pad_ms, out_path):
    orig = AudioSegment.from_file(str(original_path))
    combined = AudioSegment.empty()
    current_pos_ms = 0
    
    sorted_gaps = sorted(gaps, key=lambda x: x["audio_start"])
    
    for gap in sorted_gaps:
        if not gap.get("approved"):
            continue
            
        cut_ms = int(gap["cut_point"] * 1000)
        before_chunk = orig[current_pos_ms:cut_ms]
        before_chunk = before_chunk.fade_out(20)
        combined += before_chunk
        
        if gap.get("generated_path") and os.path.exists(gap["generated_path"]):
            gen = AudioSegment.from_wav(str(gap["generated_path"]))
            gen = gen.set_frame_rate(orig.frame_rate).set_channels(orig.channels)
            gen = gen.high_pass_filter(50)
            gen = gen.fade_in(10).fade_out(10)
            
            pad = AudioSegment.silent(duration=pause_pad_ms, frame_rate=orig.frame_rate)
            combined += pad + gen + pad
        else:
            combined += AudioSegment.silent(duration=100, frame_rate=orig.frame_rate)
            
        current_pos_ms = cut_ms
        
    after_chunk = orig[current_pos_ms:]
    after_chunk = after_chunk.fade_in(20)
    combined += after_chunk
    
    combined.export(str(out_path), format="mp3", bitrate="192k")
    return out_path

def run_ai_enhancer(input_audio_path, output_audio_path, chunk_seconds):
    audio = AudioSegment.from_file(str(input_audio_path))
    chunk_length_ms = chunk_seconds * 1000
    total_chunks = len(audio) // chunk_length_ms + 1
    
    enhanced_segments = []
    
    venv_scripts = Path(sys.executable).parent
    df_exe = venv_scripts / "deepfilternet.exe"
    if not df_exe.exists(): df_exe = venv_scripts / "deepFilter.exe"

    for i in range(total_chunks):
        start_ms = i * chunk_length_ms
        end_ms = min((i + 1) * chunk_length_ms, len(audio))
        if start_ms >= end_ms: break
        
        chunk = audio[start_ms:end_ms]
        temp_in = WORK_DIR / f"df_in_{i}.wav"
        temp_out = WORK_DIR / f"df_out_{i}.wav"
        
        chunk.export(str(temp_in), format="wav")
        
        cmd = [str(df_exe), str(temp_in), str(temp_out)]
        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=chunk_seconds + 10)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            cmd = ["deepfilternet", str(temp_in), str(temp_out)]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=chunk_seconds + 10)

        if temp_out.exists():
            enhanced_chunk = AudioSegment.from_file(str(temp_out))
            enhanced_segments.append(enhanced_chunk)
            os.remove(str(temp_in))
            os.remove(str(temp_out))
            
    if len(enhanced_segments) > 0:
        enhanced_combined = enhanced_segments[0]
        for next_chunk in enhanced_segments[1:]:
            enhanced_combined = enhanced_combined.append(next_chunk, crossfade=50)
            
        enhanced_combined.export(str(output_audio_path), format="mp3", bitrate="192k")
    else:
        raise RuntimeError("AI failed to process any chunks.")

# ==========================================
# FRONTEND UI
# ==========================================

st.set_page_config(page_title="Audiobook Toolkit", page_icon="🎧", layout="wide")

st.title("🎧 Audiobook Toolkit")

# --- Mode Selection ---
app_mode = st.radio(
    "Select a workflow:",
    ["Patch Missing Audio", "Just Remaster Audio"],
    horizontal=True
)
st.markdown("---")

# --- SIDEBAR CONFIGURATION PANEL ---
with st.sidebar:
    st.header("📁 Project Settings")
    audio_file = st.file_uploader("Chapter Audio (MP3)", type=["mp3","wav","m4a"])
    text_file  = st.file_uploader("Book Text (.txt)", type=["txt"])
    
    if app_mode == "Patch Missing Audio":
        chapter_num = st.number_input("Chapter #", 1, 27, 1, 1)

    st.markdown("---")
    
    with st.expander("⚙️ AI Configurations", expanded=False):
        
        # 1. Whisper Model
        whisper_model = st.selectbox(
            "Whisper Model Size",
            ["tiny", "base", "small", "medium"],
            index=2
        )
        with st.expander("Explain Whisper Model Size"):
            st.caption("The AI that listens to the audio. 'tiny' is fastest but makes mistakes. 'small' is the sweet spot. 'medium' is slower but best for heavy accents.")
            
        st.markdown("---")
            
        # 2. Minimum Gap Size
        min_gap_words = st.slider(
            "Minimum Gap Size (words)", 
            min_value=5, 
            max_value=50, 
            value=15
        )
        with st.expander("Explain Minimum Gap Size"):
            st.caption("How many missing words trigger a warning. 15 is good. Lower it if you want to catch tiny skipped sentences (but expect false alarms).")
            
        st.markdown("---")
        
        if app_mode == "Patch Missing Audio":
            # 3. Voice Sample
            voice_sample_sec = st.slider(
                "Voice Sample (sec) [Best: 15-30]", 
                min_value=5, 
                max_value=60, 
                value=25, 
                step=5
            )
            with st.expander("Explain Voice Sample"):
                st.caption("How many seconds of the narrator the AI listens to. 15-30s is best. Too long, and it gets confused by background noise.")
                
            st.markdown("---")
                
            # 4. Splice Padding
            pause_pad_ms = st.slider(
                "Splice Padding (ms)",
                min_value=50,
                max_value=500,
                value=150,
                step=50
            )
            with st.expander("Explain Splice Padding"):
                st.caption("The digital silence added between the narrator and the AI voice. 150ms sounds natural.")
                
            st.markdown("---")
            
        if app_mode == "Just Remaster Audio" or app_mode == "Patch Missing Audio":
            # 5. Remaster Chunk Size
            chunk_size = st.slider(
                "Remaster Chunk Size (seconds)",
                min_value=30,
                max_value=180,
                value=60,
                step=30
            )
            with st.expander("Explain Remaster Chunk Size"):
                st.caption("How much audio the cleaner processes at once. Lower this to 30s if your laptop runs out of RAM and crashes.")

# ==========================================
# FLOW 1: PATCH MISSING AUDIO
# ==========================================
if app_mode == "Patch Missing Audio":
    if not audio_file or not text_file:
        st.info("👈 Please upload your Chapter Audio and Book Text in the sidebar to begin.")
        st.stop()

    audio_path = WORK_DIR / f"chapter{chapter_num:02d}_input{Path(audio_file.name).suffix}"
    audio_path.write_bytes(audio_file.getvalue())

    full_text = text_file.getvalue().decode("utf-8", errors="replace")
    chapters  = split_chapters(full_text)
    if chapter_num not in chapters:
        st.error(f"Chapter {chapter_num} not found in text file.")
        st.stop()

    book_sentences = split_sentences(chapters[chapter_num])

    if "segments" not in st.session_state:
        st.subheader("🔍 Step 1: Transcribe & Analyze")
        st.write(f"Loaded Chapter {chapter_num} ({len(book_sentences)} sentences). The AI needs to listen to the audio to find missing text.")
        if st.button("▶ Start Transcription", type="primary"):
            with st.spinner(f"Loading Whisper '{whisper_model}' model..."):
                load_model(whisper_model)
            with st.spinner("Transcribing audio (this may take a while on CPU)..."):
                st.session_state["segments"] = transcribe_and_align(audio_path, chapter_num, whisper_model)
            with st.spinner("Aligning text..."):
                st.session_state["gaps"] = detect_gaps(st.session_state["segments"], book_sentences, min_gap_words)
            st.rerun()
        st.stop()

    gaps = st.session_state["gaps"]
    if not gaps:
        st.success("✅ No gaps detected! The audio perfectly matches the book text.")
        st.stop()

    # Gap Selector
    st.subheader("🎯 Select a Gap")
    gap_options = [f"Gap {i+1}: ~{len(g['missing_text'].split())} words missing" for i, g in enumerate(gaps)]
    selected_idx = st.selectbox("Choose a gap to work on:", range(len(gaps)), format_func=lambda x: gap_options[x])
    gap = gaps[selected_idx]

    # --- STEP 2: Text and Cut Point Side-by-Side ---
    st.markdown("---")
    st.subheader("📝 Step 2: Edit Text & Find Cut Point")
    st.write("Review the missing text and set the exact audio cut point.")
    
    col_text, col_cut = st.columns(2)
    
    with col_text:
        st.markdown("**Missing Text (editable):**")
        st.info(f"**Before:** *...{gap['before_book']}*")
        st.info(f"**After:** *{gap['after_book']}...*")
        edited = st.text_area("missing_text", gap["missing_text"], height=200, key=f"txt_{selected_idx}", label_visibility="collapsed")
        gap["missing_text_edited"] = edited
        st.caption("Tip: Leave blank to delete this audio segment. Fix dashes and foreign words manually.")

    with col_cut:
        st.markdown("**Find the Cut Point:**")
        preview_start = max(0, gap["audio_start"] - 5)
        preview_end = gap["audio_start"] + 5
        preview_audio = AudioSegment.from_file(str(audio_path))[int(preview_start*1000):int(preview_end*1000)]
        preview_path = WORK_DIR / f"preview_{selected_idx}_{int(time.time())}.wav"
        preview_audio.export(str(preview_path), format="wav")
        
        st.info(f"⏱️ This player starts at **{format_time(preview_start)}** in the full chapter.")
        st.audio(str(preview_path))
        
        rel_sec = st.number_input(
            "Type the exact second from the player above where the cut occurs:", 
            min_value=0.0, max_value=10.0, value=5.0, step=0.05, format="%.2f", key=f"rel_{selected_idx}"
        )
        gap["cut_point"] = preview_start + rel_sec
        st.success(f"**Calculated Cut Time:** {format_time(gap['cut_point'])}")

    # --- STEP 3: Voice Generation ---
    st.markdown("---")
    st.subheader("🎙️ Step 3: Generate Voice")
    st.write("The AI needs a sample of the narrator's voice to learn from. If the default sample sounds noisy, shift it back.")
    
    col_ref, col_gen = st.columns(2)
    with col_ref:
        ref_shift = st.slider("Shift reference backward (seconds)", min_value=0, max_value=60, value=0, step=5, key=f"shift_{selected_idx}")
        if st.button("🔊 Preview Reference Clip", key=f"ref_preview_{selected_idx}", use_container_width=True):
            ref_path = extract_reference(audio_path, gap["cut_point"], voice_sample_sec, ref_shift)
            st.audio(str(ref_path))
        gap["ref_shift"] = ref_shift

    with col_gen:
        gap["approved"] = st.checkbox("Approve this gap", key=f"ap_{selected_idx}", value=gap.get("approved", False))
        if gap["approved"] and gap["missing_text_edited"].strip():
            if st.button(f"🎙️ Generate Voice for Gap {selected_idx+1}", type="primary", use_container_width=True):
                with st.spinner("Generating voice..."):
                    ref = extract_reference(audio_path, gap["cut_point"], voice_sample_sec, gap["ref_shift"])
                    out = WORK_DIR / f"gap_{selected_idx}_{int(time.time())}.wav"
                    generate_clip(gap["missing_text_edited"], ref, out)
                    gap["generated_path"] = str(out)
                    gap["ref_path"] = str(ref)
                st.rerun()
        elif gap["approved"] and not gap["missing_text_edited"].strip():
            st.warning("⚠️ Text box is empty. This audio segment will be **deleted** when you save.")
            
    # Raw Audio Player
    if gap.get("generated_path") and os.path.exists(gap["generated_path"]):
        st.markdown("**Generated AI Voice (Raw):**")
        st.audio(gap["generated_path"])

    # --- STEP 4: EXPORT ---
    ready_gaps = [g for g in gaps if g.get("approved")]
    if ready_gaps:
        st.markdown("---")
        st.subheader("💾 Step 4: Export Final Audio")
        
        col_export1, col_export2 = st.columns(2)
        with col_export1:
            if st.button("💾 Generate Spliced Version", use_container_width=True):
                out_mp3 = OUTPUT_DIR / f"chapter{chapter_num:02d}_patched.mp3"
                with st.spinner("Splicing audio file..."):
                    rebuild_audio(audio_path, gaps, pause_pad_ms, out_mp3)
                st.session_state["patched_path"] = str(out_mp3)
                st.rerun()
        with col_export2:
            if st.button("✨ Generate AI Remastered Version", type="primary", use_container_width=True):
                out_mp3 = OUTPUT_DIR / f"chapter{chapter_num:02d}_patched_remastered.mp3"
                temp_mp3 = WORK_DIR / f"temp_patched_{int(time.time())}.mp3"
                with st.spinner("Splicing audio file..."):
                    rebuild_audio(audio_path, gaps, pause_pad_ms, temp_mp3)
                with st.spinner(f"AI is cleaning the audio in {chunk_size}-second chunks..."):
                    try:
                        run_ai_enhancer(temp_mp3, out_mp3, chunk_size)
                        st.session_state["patched_path"] = str(out_mp3)
                        st.rerun()
                    except Exception as e:
                        st.error(f"AI Remaster failed: {e}")

    if st.session_state.get("patched_path"):
        p = Path(st.session_state["patched_path"])
        st.markdown("---")
        st.success(f"Audio generated successfully!")
        st.audio(str(p))
        with open(p, "rb") as f:
            st.download_button("⬇️ Save Audio File", f.read(), file_name=p.name, mime="audio/mpeg", type="primary", use_container_width=True)


# ==========================================
# FLOW 2: JUST REMASTER AUDIO
# ==========================================
elif app_mode == "Just Remaster Audio":
    st.subheader("✨ AI Audio Remastering")
    st.write("Upload an audio file to clean up background noise and hiss using DeepFilterNet. No transcription or gap detection is performed here.")
    
    if not audio_file:
        st.info("👈 Please upload an audio file in the sidebar to begin.")
        st.stop()
        
    audio_path = WORK_DIR / f"remaster_input{Path(audio_file.name).suffix}"
    audio_path.write_bytes(audio_file.getvalue())
    
    st.success("Audio uploaded successfully.")
    
    if st.button("▶ Run AI Remaster", type="primary", use_container_width=True):
        out_mp3 = OUTPUT_DIR / f"{Path(audio_file.name).stem}_remastered.mp3"
        with st.spinner(f"AI is cleaning the audio in {chunk_size}-second chunks..."):
            try:
                run_ai_enhancer(audio_path, out_mp3, chunk_size)
                st.session_state["remastered_path"] = str(out_mp3)
                st.rerun()
            except Exception as e:
                st.error(f"AI Remaster failed: {e}")
                
    if st.session_state.get("remastered_path"):
        p = Path(st.session_state["remastered_path"])
        st.markdown("---")
        st.success("Audio remastered successfully!")
        st.audio(str(p))
        with open(p, "rb") as f:
            st.download_button("⬇️ Save Audio File", f.read(), file_name=p.name, mime="audio/mpeg", type="primary", use_container_width=True)