# YouTube Video Summarizer

An AI-powered tool that summarizes YouTube videos in multiple languages. Just paste a URL and get a summary, key points, and timestamps.

## Features

- **Multi-language support** - English, Spanish, French, German, Hindi, Telugu, and more
- **Works with long videos** - Automatically chunks and summarizes
- **Video thumbnail preview** - Shows thumbnail when you paste URL
- **Summary length options** - Short, Medium, or Detailed
- **Download as TXT** - Save your summary locally
- **Progress indicators** - See real-time processing status

## How It Works

1. **Paste YouTube URL** - Enter any YouTube video link
2. **Select language** - Choose the transcript language
3. **Choose length** - Short, Medium, or Detailed summary
4. **Get results** - Summary, key points, and timestamps

## Tech Stack

- **Groq API** - Fast LLM inference (Llama 3.1 8B)
- **Gradio** - Web interface
- **youtube-transcript-api** - Fetch video captions
- **Python** - Backend logic

## Setup

1. Clone the repo:
```bash
git clone https://github.com/archana-gurimitkala/youtube-video-summarizer.git
cd youtube-video-summarizer
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Add your Groq API key:
```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

4. Run the app:
```bash
python app.py
```

5. Open http://localhost:7861

## Get Groq API Key

1. Go to https://console.groq.com
2. Sign up for free
3. Create an API key
4. Add it to your `.env` file

## Screenshots

*Add your screenshots here*

## License

MIT

---

*Built with Groq and Gradio*
