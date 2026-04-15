---
title: Youtube Summarizer
emoji: 🎬
colorFrom: red
colorTo: yellow
sdk: gradio
sdk_version: 5.25.0
app_file: app.py
pinned: false
license: mit
short_description: YouTube video summarizer using Groq AI and LLaMA 3
---

# YouTube Video Summarizer 🎬

I got tired of scrubbing through long YouTube videos just to find the two minutes that were actually relevant to me. So I built this — paste a URL, pick how detailed you want the summary, and it pulls the transcript and summarizes it almost instantly using Groq. It supports 12+ languages and handles long videos by chunking them automatically.

## What It Does

You know those 45-minute videos where you just need the main points? This tool watches them for you (kind of).

- Paste any YouTube URL
- Pick your language
- Choose how detailed you want it
- Get a clean summary in seconds

## Features

-  **12+ languages** - English, Hindi, Telugu, Spanish, French, and more
-  **Long videos? No problem** - Automatically breaks them into chunks
-  **Thumbnail preview** - See what you're summarizing
-  **Flexible length** - Short, Medium, or Detailed
-  **Download option** - Save as TXT file

## How I Built This

- **Groq API** - Super fast AI inference (Llama 3.1 8B)
- **Gradio** - Simple web interface
- **youtube-transcript-api** - Pulls captions from YouTube
- **Python** - Glues everything together

## Try It Yourself

1. Clone this repo:
```bash
git clone https://github.com/archana-gurimitkala/-groq-youtube-summarizer-.git
cd -groq-youtube-summarizer-
```

2. Install stuff:
```bash
pip install -r requirements.txt
```

3. Get your free Groq API key from https://console.groq.com

4. Create `.env` file:
```
GROQ_API_KEY=your-key-here
```

5. Run it:
```bash
python app.py
```

6. Open http://localhost:7861 and start summarizing!

## Screenshots

![Screenshot 1](screenshots/YVS1.png)
![Screenshot 2](screenshots/YVS2.png)
![Screenshot 3](screenshots/YVS3.png)
![Screenshot 4](screenshots/YVS4.png)
![Screenshot 5](screenshots/YVS5.png)
![Screenshot 6](screenshots/YVS6.png)
![Screenshot 7](screenshots/YVS7.png)
![Screenshot 8](screenshots/YVS8.png)
![Screenshot 9](screenshots/YVS9.png)
![Screenshot 10](screenshots/YVS10.png)

---

*Built because I got tired of watching entire videos for 2 minutes of useful content* 😅
