# Agentic Product Scraper

AI-powered web automation using computer vision and LLM reasoning.

## Quick Start

1. **Activate Environment**
   ```bash
   .venv\Scripts\activate
   ```

2. **Run Agent**
   ```bash
   # Search Google
   python scripts/run_agent.py "search for cats" --url "https://www.google.com"
   
   # Search DuckDuckGo
   python scripts/run_agent.py "search for cars" --url "https://www.duckduckgo.com"
   
   # YouTube automation
   python scripts/run_agent.py "search for song and play it" --url "https://www.youtube.com"
   ```

## Features

- **Computer Vision**: YOLO model detects UI elements (buttons, fields, links)
- **AI Reasoning**: Azure OpenAI plans actions based on detected elements
- **Browser Automation**: Playwright executes clicks, typing, navigation
- **Visual Mode**: Watch the AI navigate in real-time (headless=false)

## Configuration

Edit `runner/config.py`:
- `HEADLESS`: Set to `true` for background operation
- `YOLO_MODEL_PATH`: Path to UI detection model

## API Server (Optional)

```bash
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

## Requirements

- Python 3.12+
- Azure OpenAI API key (set in `.env`)
- Virtual environment activated

## How It Works

1. **Perception**: Screenshot → YOLO detects UI elements
2. **Reasoning**: LLM analyzes elements and plans next action
3. **Action**: Playwright executes the planned action
4. **Repeat**: Until goal is achieved

The AI can handle complex multi-step tasks across different websites.
