"""
YouTube Video Summarizer using Groq API
Paste a YouTube URL → Get summary, key points, and timestamps
Handles long videos by chunking
"""

import gradio as gr
import os
import re
import time
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


def extract_video_id(url):
    """Extract video ID from YouTube URL."""
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
    """Show thumbnail when URL is entered."""
    video_id = extract_video_id(youtube_url)
    if video_id:
        # Use hqdefault as it's always available
        thumb_url = f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        return f'<img src="{thumb_url}" style="max-width:100%; border-radius:8px;" onerror="this.src=\'https://img.youtube.com/vi/{video_id}/default.jpg\'">'
    return ""


def get_transcript(video_id, language="auto"):
    """Get transcript from YouTube video."""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)

        transcript = None
        lang_codes = {
            "auto": None,
            "English": ['en', 'en-US', 'en-GB'],
            "Spanish": ['es', 'es-ES', 'es-MX'],
            "French": ['fr', 'fr-FR'],
            "German": ['de', 'de-DE'],
            "Hindi": ['hi', 'hi-IN'],
            "Telugu": ['te', 'te-IN'],
            "Portuguese": ['pt', 'pt-BR', 'pt-PT'],
            "Japanese": ['ja'],
            "Korean": ['ko'],
            "Chinese": ['zh', 'zh-CN', 'zh-TW'],
            "Arabic": ['ar'],
            "Russian": ['ru'],
        }

        try:
            if language != "auto" and language in lang_codes:
                transcript = transcript_list.find_transcript(lang_codes[language])
            else:
                # Try English first, then any available
                try:
                    transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
                except:
                    for t in transcript_list:
                        transcript = t
                        break
        except:
            for t in transcript_list:
                transcript = t
                break

        if transcript is None:
            return None, "No transcripts available for this video"

        fetched = transcript.fetch()

        full_transcript = ""
        for entry in fetched:
            timestamp = int(entry.start)
            minutes = timestamp // 60
            seconds = timestamp % 60
            text = entry.text
            full_transcript += f"[{minutes:02d}:{seconds:02d}] {text}\n"

        return full_transcript, None
    except Exception as e:
        return None, f"Error getting transcript: {str(e)}"


def chunk_transcript(transcript, chunk_size=3000):
    """Split transcript into chunks."""
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
    """Summarize a single chunk."""
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
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=500,
    )

    return response.choices[0].message.content


def combine_summaries(chunk_summaries, settings):
    """Combine chunk summaries into final summary."""
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
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=settings['max_tokens'],
    )

    return response.choices[0].message.content


def summarize_video(youtube_url, language="auto", summary_length="Medium", progress=gr.Progress()):
    """Main function to summarize YouTube video."""

    if not youtube_url.strip():
        return "Please enter a YouTube URL", "", ""

    # Set parameters based on summary length
    length_settings = {
        "Short": {"paragraphs": "1", "points": "3-4", "timestamps": "3", "max_tokens": 800},
        "Medium": {"paragraphs": "2-3", "points": "5-7", "timestamps": "5", "max_tokens": 1500},
        "Detailed": {"paragraphs": "4-5", "points": "8-10", "timestamps": "8-10", "max_tokens": 2500},
    }
    settings = length_settings.get(summary_length, length_settings["Medium"])

    video_id = extract_video_id(youtube_url)
    if not video_id:
        return "Invalid YouTube URL", "", ""

    transcript, error = get_transcript(video_id, language)
    if error:
        return error, "", ""

    try:
        # Check if transcript is long
        if len(transcript) > 4000:
            # Chunk and summarize
            chunks = chunk_transcript(transcript, chunk_size=3000)

            chunk_summaries = []
            for i, chunk in enumerate(chunks, 1):
                progress(i / (len(chunks) + 1), desc=f"Processing chunk {i}/{len(chunks)}...")
                summary = summarize_chunk(chunk, i, len(chunks))
                chunk_summaries.append(summary)

            progress(1, desc="Combining summaries...")
            # Combine all summaries
            result = combine_summaries(chunk_summaries, settings)
        else:
            # Short video - summarize directly
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

        # Parse result into sections
        summary = ""
        key_points = ""
        timestamps = ""

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

    except Exception as e:
        return f"Error: {str(e)}", "", ""


def create_download_file(summary, key_points, timestamps):
    """Create a text file with the summary results."""
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
Powered by Groq (Llama 3.1 8B)
"""
    # Save to temp file
    import tempfile
    filepath = os.path.join(tempfile.gettempdir(), "video_summary.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


# Gradio UI
with gr.Blocks(title="YouTube Video Summarizer") as demo:
    gr.Markdown("# 🎬 YouTube Video Summarizer")

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
                length_input = gr.Dropdown(label="Length", choices=["Short", "Medium", "Detailed"], value="Medium")
                submit_btn = gr.Button("Summarize", variant="primary")
        with gr.Column(scale=1):
            thumbnail_output = gr.HTML()

    with gr.Row():
        summary_output = gr.Textbox(label="Summary", lines=5, interactive=False)

    with gr.Row():
        keypoints_output = gr.Textbox(label="Key Points", lines=5, interactive=False)
        timestamps_output = gr.Textbox(label="Timestamps", lines=5, interactive=False)

    with gr.Row():
        download_btn = gr.Button("📥 Download as TXT", variant="secondary", scale=1)
        download_file = gr.File(label="Download", file_count="single", scale=2)

    # Show thumbnail when URL is entered
    url_input.change(
        fn=show_thumbnail,
        inputs=url_input,
        outputs=thumbnail_output
    )

    # Summarize button click
    submit_btn.click(
        fn=summarize_video,
        inputs=[url_input, language_input, length_input],
        outputs=[summary_output, keypoints_output, timestamps_output]
    )

    # Download button click
    download_btn.click(
        fn=create_download_file,
        inputs=[summary_output, keypoints_output, timestamps_output],
        outputs=download_file
    )



if __name__ == "__main__":
    print("Starting YouTube Video Summarizer...")
    demo.launch(server_port=7861)
