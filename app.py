"""
YouTube Video Summarizer using Groq API
Features: Summarize, Status Updates, Chat with Video, Translate, Export PDF/TXT
"""

import gradio as gr
import os
import re
import tempfile
import requests
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY")


def extract_video_id(url):
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def show_thumbnail(youtube_url):
    video_id = extract_video_id(youtube_url)
    if video_id:
        thumb_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        return f'<img src="{thumb_url}" style="max-width:100%; border-radius:8px;" onerror="this.src=\'https://img.youtube.com/vi/{video_id}/default.jpg\'">'
    return ""


def get_transcript_supadata(video_id, language="auto"):
    try:
        lang_codes = {
            "auto": None, "English": "en", "Spanish": "es", "French": "fr",
            "German": "de", "Hindi": "hi", "Telugu": "te", "Portuguese": "pt",
            "Japanese": "ja", "Korean": "ko", "Chinese": "zh", "Arabic": "ar", "Russian": "ru",
        }
        params = {"videoId": video_id}
        if language != "auto" and language in lang_codes:
            params["lang"] = lang_codes[language]

        response = requests.get(
            "https://api.supadata.ai/v1/youtube/transcript",
            headers={"x-api-key": SUPADATA_API_KEY},
            params=params,
            timeout=30,
        )
        if response.status_code not in (200, 206):
            return None

        data = response.json()
        content = data.get("content", [])
        if not content:
            return None

        full_transcript = ""
        for entry in content:
            offset_ms = entry.get("offset", 0)
            seconds_total = int(offset_ms / 1000)
            minutes = seconds_total // 60
            seconds = seconds_total % 60
            text = entry.get("text", "")
            full_transcript += f"[{minutes:02d}:{seconds:02d}] {text}\n"
        return full_transcript
    except Exception:
        return None


def transcribe_audio_file(audio_path):
    """Transcribe an audio file using Groq Whisper."""
    try:
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        if file_size_mb > 24:
            return None, "Audio file too large (max 25MB). Try a shorter clip."

        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_path), audio_file),
                model="whisper-large-v3",
                response_format="verbose_json",
            )

        full_transcript = ""
        if hasattr(transcription, "segments") and transcription.segments:
            for seg in transcription.segments:
                start = int(seg.get("start", 0))
                minutes = start // 60
                seconds = start % 60
                text = seg.get("text", "").strip()
                full_transcript += f"[{minutes:02d}:{seconds:02d}] {text}\n"
        else:
            full_transcript = transcription.text

        return full_transcript, None
    except Exception as e:
        return None, f"Transcription error: {str(e)}"


def chunk_transcript(transcript, chunk_size=3000):
    chunks = []
    lines = transcript.split('\n')
    current_chunk = ""
    for line in lines:
        if len(current_chunk) + len(line) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def summarize_chunk(chunk, chunk_num, total_chunks):
    prompt = f"""Summarize this part ({chunk_num}/{total_chunks}) of a video transcript.
Give a brief summary (2-3 sentences) and list 2-3 key points.

TRANSCRIPT PART {chunk_num}:
{chunk}

Format:
SUMMARY: [your summary]
KEY POINTS:
- point 1
- point 2
"""
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=500,
    )
    return response.choices[0].message.content


def combine_summaries(chunk_summaries, settings):
    combined = "\n\n".join(chunk_summaries)
    prompt = f"""Combine these partial summaries into one cohesive summary.

PARTIAL SUMMARIES:
{combined}

Provide:
1. SUMMARY ({settings['paragraphs']} paragraphs covering the whole video)
2. KEY POINTS ({settings['points']} most important points from the entire video)
3. Suggest {settings['timestamps']} important TIMESTAMPS to watch

Format clearly with headers: SUMMARY, KEY POINTS, TIMESTAMPS"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=settings['max_tokens'],
    )
    return response.choices[0].message.content


def parse_result(result):
    summary = key_points = timestamps = ""
    if "KEY POINTS" in result.upper():
        parts = re.split(r'KEY\s*POINTS', result, flags=re.IGNORECASE)
        summary = parts[0].replace("SUMMARY", "").replace("**", "").strip()
        rest = parts[1] if len(parts) > 1 else ""
        if "TIMESTAMP" in rest.upper():
            kp_parts = re.split(r'TIMESTAMP', rest, flags=re.IGNORECASE)
            key_points = kp_parts[0].replace("**", "").strip()
            timestamps = kp_parts[1].replace("**", "").replace("S", "", 1).strip() if len(kp_parts) > 1 else ""
        else:
            key_points = rest.replace("**", "").strip()
    else:
        summary = result
    return summary, key_points, timestamps


def summarize_video(youtube_url, language, summary_length):
    """Generator: yields (summary, key_points, timestamps, status, transcript)"""

    if not youtube_url.strip():
        yield "Please enter a YouTube URL", "", "", "", ""
        return

    length_settings = {
        "Short": {"paragraphs": "1", "points": "3-4", "timestamps": "3", "max_tokens": 800},
        "Medium": {"paragraphs": "2-3", "points": "5-7", "timestamps": "5", "max_tokens": 1500},
        "Detailed": {"paragraphs": "4-5", "points": "8-10", "timestamps": "8-10", "max_tokens": 2500},
    }
    settings = length_settings.get(summary_length, length_settings["Medium"])

    video_id = extract_video_id(youtube_url)
    if not video_id:
        yield "Invalid YouTube URL", "", "", "", ""
        return

    yield "", "", "", "📋 Checking for captions...", ""
    transcript = get_transcript_supadata(video_id, language)

    if transcript:
        yield "", "", "", "✅ Captions found! Starting summarization...", ""
    else:
        yield (
            "⚠️ This video has no captions. Please upload the audio file below to transcribe it.",
            "", "", "❌ No captions found", ""
        )
        return

    try:
        if len(transcript) > 4000:
            chunks = chunk_transcript(transcript, chunk_size=3000)
            chunk_summaries = []
            for i, chunk in enumerate(chunks, 1):
                yield "", "", "", f"🤖 Processing part {i} of {len(chunks)}...", ""
                chunk_summaries.append(summarize_chunk(chunk, i, len(chunks)))

            yield "", "", "", "🔗 Combining all parts...", ""
            result = combine_summaries(chunk_summaries, settings)
        else:
            yield "", "", "", "🤖 Summarizing with AI...", ""
            prompt = f"""Analyze this YouTube video transcript and provide:

1. **SUMMARY** ({settings['paragraphs']} paragraphs)
2. **KEY POINTS** ({settings['points']} bullet points)
3. **TIMESTAMPS** ({settings['timestamps']} important moments with [MM:SS] format)

TRANSCRIPT:
{transcript}"""

            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an expert video content analyzer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=settings['max_tokens'],
            )
            result = response.choices[0].message.content

        summary, key_points, timestamps = parse_result(result)
        yield summary, key_points, timestamps, "✅ Done!", transcript

    except Exception as e:
        yield f"Error: {str(e)}", "", "", "❌ Error occurred", ""


def chat_with_video(message, history, transcript):
    try:
        if not message.strip():
            return history or [], ""

        history = history or []

        if not transcript:
            history.append({"role": "assistant", "content": "Please summarize a video first, then I can answer questions about it!"})
            return history, ""

        api_messages = [
            {"role": "system", "content": f"You are a helpful assistant. Answer questions based on this video transcript:\n\n{transcript[:8000]}"},
        ]
        for msg in history:
            api_messages.append({"role": msg["role"], "content": msg["content"]})
        api_messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=api_messages,
            temperature=0.5,
            max_tokens=1000,
        )
        reply = response.choices[0].message.content
        history.append({"role": "user", "content": message})
        history.append({"role": "assistant", "content": reply})
        return history, ""

    except Exception as e:
        history = history or []
        history.append({"role": "assistant", "content": f"Error: {str(e)}"})
        return history, ""


def translate_summary(summary, key_points, target_language):
    if not summary or not summary.strip():
        return "Please summarize a video first."

    text = f"SUMMARY:\n{summary}\n\nKEY POINTS:\n{key_points}"
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": f"Translate the following text to {target_language}. Keep the formatting and structure:\n\n{text}"}
        ],
        temperature=0.3,
        max_tokens=2000,
    )
    return response.choices[0].message.content


def create_txt(summary, key_points, timestamps):
    if not summary or summary.strip() == "":
        return None
    content = f"""YOUTUBE VIDEO SUMMARY
{'='*50}

SUMMARY:
{summary}

KEY POINTS:
{key_points}

IMPORTANT TIMESTAMPS:
{timestamps}

{'='*50}
Generated by YouTube Video Summarizer
Powered by Groq (Llama 3.1 8B + Whisper)
"""
    filepath = os.path.join(tempfile.gettempdir(), "video_summary.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def create_pdf(summary, key_points, timestamps):
    if not summary or summary.strip() == "":
        return None

    from fpdf import FPDF

    def safe(text):
        return text.encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(15, 15, 15)

    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "YouTube Video Summary", ln=True, align="C")
    pdf.set_draw_color(200, 0, 0)
    pdf.set_line_width(0.5)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)

    if summary:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "SUMMARY", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, safe(summary))
        pdf.ln(4)

    if key_points:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "KEY POINTS", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, safe(key_points))
        pdf.ln(4)

    if timestamps:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "TIMESTAMPS", ln=True)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, safe(timestamps))

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 6, "Generated by YouTube Video Summarizer | Powered by Groq", align="C")

    filepath = os.path.join(tempfile.gettempdir(), "video_summary.pdf")
    pdf.output(filepath)
    return filepath


def summarize_audio(audio_path, summary_length):
    """Transcribe uploaded audio and summarize."""
    if not audio_path:
        yield "Please upload an audio file.", "", "", "❌ No file", ""
        return

    length_settings = {
        "Short": {"paragraphs": "1", "points": "3-4", "timestamps": "3", "max_tokens": 800},
        "Medium": {"paragraphs": "2-3", "points": "5-7", "timestamps": "5", "max_tokens": 1500},
        "Detailed": {"paragraphs": "4-5", "points": "8-10", "timestamps": "8-10", "max_tokens": 2500},
    }
    settings = length_settings.get(summary_length, length_settings["Medium"])

    yield "", "", "", "🎙️ Transcribing audio with Whisper...", ""
    transcript, error = transcribe_audio_file(audio_path)
    if not transcript:
        yield error, "", "", "❌ Transcription failed", ""
        return

    yield "", "", "", "🤖 Summarizing...", ""
    try:
        if len(transcript) > 4000:
            chunks = chunk_transcript(transcript, chunk_size=3000)
            chunk_summaries = []
            for i, chunk in enumerate(chunks, 1):
                yield "", "", "", f"🤖 Processing part {i} of {len(chunks)}...", ""
                chunk_summaries.append(summarize_chunk(chunk, i, len(chunks)))
            yield "", "", "", "🔗 Combining all parts...", ""
            result = combine_summaries(chunk_summaries, settings)
        else:
            prompt = f"""Analyze this video transcript and provide:

1. **SUMMARY** ({settings['paragraphs']} paragraphs)
2. **KEY POINTS** ({settings['points']} bullet points)
3. **TIMESTAMPS** ({settings['timestamps']} important moments with [MM:SS] format)

TRANSCRIPT:
{transcript}"""
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an expert video content analyzer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=settings['max_tokens'],
            )
            result = response.choices[0].message.content

        summary, key_points, timestamps = parse_result(result)
        yield summary, key_points, timestamps, "✅ Done!", transcript
    except Exception as e:
        yield f"Error: {str(e)}", "", "", "❌ Error", ""


# Gradio UI
with gr.Blocks(title="YouTube Video Summarizer") as demo:
    gr.Markdown("# 🎬 YouTube Video Summarizer")
    transcript_state = gr.State("")

    with gr.Row():
        with gr.Column(scale=3):
            url_input = gr.Textbox(label="YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
            with gr.Row():
                language_input = gr.Dropdown(
                    label="Language",
                    choices=["auto", "English", "Spanish", "French", "German", "Hindi", "Telugu",
                             "Portuguese", "Japanese", "Korean", "Chinese", "Arabic", "Russian"],
                    value="auto",
                )
                length_input = gr.Dropdown(label="Summary Length", choices=["Short", "Medium", "Detailed"], value="Medium")
                submit_btn = gr.Button("🚀 Summarize", variant="primary")
        with gr.Column(scale=1):
            thumbnail_output = gr.HTML()

    status_output = gr.Markdown("")

    # Audio upload fallback
    with gr.Accordion("🎵 No captions? Upload audio file instead", open=False):
        gr.Markdown("If the video has no captions, download the audio manually and upload it here for transcription.")
        audio_upload = gr.Audio(label="Upload Audio (MP3/WAV/M4A, max 25MB)", type="filepath")
        audio_btn = gr.Button("🎙️ Transcribe & Summarize Audio", variant="secondary")

    with gr.Row():
        summary_output = gr.Textbox(label="📝 Summary", lines=6, interactive=False)

    with gr.Row():
        keypoints_output = gr.Textbox(label="✅ Key Points", lines=5, interactive=False)
        timestamps_output = gr.Textbox(label="⏱️ Timestamps", lines=5, interactive=False)

    # Translation
    gr.Markdown("---\n### 🌐 Translate Summary")
    with gr.Row():
        translate_lang = gr.Dropdown(
            label="Translate To",
            choices=["Telugu", "Hindi", "Spanish", "French", "German", "Portuguese",
                     "Japanese", "Korean", "Chinese", "Arabic", "Russian", "English"],
            value="Telugu",
            scale=2,
        )
        translate_btn = gr.Button("🌐 Translate", variant="secondary", scale=1)
    translated_output = gr.Textbox(label="Translated Summary", lines=5, interactive=False)

    # Downloads
    gr.Markdown("---\n### 💾 Export")
    with gr.Row():
        download_txt_btn = gr.Button("📥 Download TXT", variant="secondary")
        download_pdf_btn = gr.Button("📄 Download PDF", variant="secondary")
    with gr.Row():
        download_txt_file = gr.File(label="TXT File", file_count="single")
        download_pdf_file = gr.File(label="PDF File", file_count="single")

    # Chat
    gr.Markdown("---\n### 💬 Chat with this Video")
    chatbot = gr.Chatbot(label="Ask anything about the video", type="messages", height=350)
    with gr.Row():
        chat_input = gr.Textbox(label="Your question", placeholder="What is this video about?", scale=4)
        chat_btn = gr.Button("Send", variant="primary", scale=1)

    # Events
    url_input.change(fn=show_thumbnail, inputs=url_input, outputs=thumbnail_output)

    submit_btn.click(
        fn=summarize_video,
        inputs=[url_input, language_input, length_input],
        outputs=[summary_output, keypoints_output, timestamps_output, status_output, transcript_state],
    )

    translate_btn.click(
        fn=translate_summary,
        inputs=[summary_output, keypoints_output, translate_lang],
        outputs=translated_output,
    )

    audio_btn.click(
        fn=summarize_audio,
        inputs=[audio_upload, length_input],
        outputs=[summary_output, keypoints_output, timestamps_output, status_output, transcript_state],
    )

    download_txt_btn.click(fn=create_txt, inputs=[summary_output, keypoints_output, timestamps_output], outputs=download_txt_file)
    download_pdf_btn.click(fn=create_pdf, inputs=[summary_output, keypoints_output, timestamps_output], outputs=download_pdf_file)

    chat_btn.click(fn=chat_with_video, inputs=[chat_input, chatbot, transcript_state], outputs=[chatbot, chat_input])
    chat_input.submit(fn=chat_with_video, inputs=[chat_input, chatbot, transcript_state], outputs=[chatbot, chat_input])


if __name__ == "__main__":
    print("Starting YouTube Video Summarizer...")
    demo.launch(server_name="0.0.0.0", server_port=7860)
