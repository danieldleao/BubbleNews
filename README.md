# BUBBLE NEWS (Version 0.1 Beta)

**Personal-use, command-line-based news aggregation and AI summarization tool for Windows 10 (and cross-platform).**

BUBBLE NEWS collects RSS feeds from your custom categories, fetches the full articles published over the previous 12 hours, uses Google Gemini to deduplicate and consolidate related stories across different reporting sources, and delivers a clean, professional HTML newsletter directly to your inbox via Disroot SMTP.

---

## Architecture & Design Principles

BUBBLE NEWS enforces a strict architectural boundary between mechanical deterministic operations and intellectual AI processing:

```text
                 WINDOWS
                    │
                    │ (Scheduled Trigger / Manual Execution)
                    ▼
          run_bubble_news.py
                    │
                    ▼
            bubble_news.py
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
     RSS Feeds            Google Gemini
   (Mechanical)           (Intellectual)
          │                   │
          └─────────┬─────────┘
                    ▼
                HTML Email
                    │
                    ▼
              Disroot SMTP
```

### 1. Python performs mechanical work:
- Reading and validating the JSON feed configuration.
- Downloading and parsing RSS feeds.
- Filtering articles to the last 12 hours (UTC-aware date parsing).
- Extracting main article text, metadata, and images using Trafilatura and BeautifulSoup.
- Preparing structured input for Google Gemini.
- Validating the AI's structured JSON response.
- Generating modern, responsive, sober HTML newsletter markup.
- Delivering the email via Disroot SMTP (Port 587, STARTTLS).
- Logging execution.

### 2. Google Gemini performs intellectual work:
- Identifying duplicate news stories across different outlets.
- Grouping articles covering the exact same event.
- Consolidating multi-source coverage into unified stories while preserving distinctive facts, figures, and quotes.
- Categorizing stories within the user-defined category structure.
- Producing informative, concise summaries answering Who, What, Where, When, and Why.

---

## Project Structure

```text
BubbleNews/
├── bubble_news.json      # User-defined taxonomy & RSS feed URLs
├── config.py             # Core configuration (Credentials, AI, Schedule)
├── bubble_news.py        # Core mechanical & intellectual pipeline
├── run_bubble_news.py    # Simple runner entry point
├── requirements.txt      # External Python dependencies
├── .gitignore            # Version control exclusion rules
└── README.md             # Documentation & guide
```

---

## Quick Start

### 1. Install Dependencies
You can run `setup.bat` or install manually via pip:
```bash
pip install -r requirements.txt
```

### 2. Configure Settings & Secrets (`.env` or `config.py`)
Copy `.env.example` to `.env` and fill in your credentials (recommended for security):

```bash
copy .env.example .env
```

Open `.env` (or `config.py`) and update with your personal settings:

```dotenv
# Email Delivery (Disroot SMTP)
EMAIL_ADDRESS=your-email@disroot.org
EMAIL_PASSWORD=YOUR_EMAIL_PASSWORD
SMTP_SERVER=disroot.org
SMTP_PORT=587

# AI Engine (Google Gemini - get your key at https://aistudio.google.com)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GEMINI_MODEL=gemini-2.5-flash

# Schedule (Single Source of Truth)
SCHEDULE_TIME=08:00
```


---

## Execution & Runner

`run_bubble_news.py` is the execution runner for Bubble News. It can be triggered manually or called automatically by the operating system.

### Manual / On-Demand Execution
To run Bubble News immediately and deliver your newsletter:
```bash
python run_bubble_news.py
```

To test news extraction without sending an email (generates `preview_newsletter.html` locally):
```bash
python run_bubble_news.py --dry-run
```

You can also specify a custom time window (in hours):
```bash
python run_bubble_news.py --hours 24
```

---

## Automated Scheduling (Windows Task Scheduler)

Windows 10 Task Scheduler is responsible for waking up and calling the runner at your designated `SCHEDULE_TIME`.

To register a daily scheduled task in Windows, open Command Prompt or PowerShell and run:

```cmd
schtasks /Create /TN "BubbleNews" /TR "python \"%CD%\run_bubble_news.py\"" /SC DAILY /ST 08:00 /F
```

*(Replace `08:00` with the `SCHEDULE_TIME` you configured in `config.py`.)*

To check task status or remove it:
```cmd
# Check status
schtasks /Query /TN "BubbleNews"

# Delete task
schtasks /Delete /TN "BubbleNews" /F
```

---

## Customizing RSS Feeds (`bubble_news.json`)

The user defines categories and RSS feeds in `bubble_news.json`. You can customize this file at any time:

```json
{
    "Technology": [
        "https://feeds.arstechnica.com/arstechnica/index",
        "https://www.theverge.com/rss/index.xml",
        "https://techcrunch.com/feed/"
    ],
    "World": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "https://www.aljazeera.com/xml/rss/all.xml"
    ],
    "Science": [
        "https://phys.org/rss-feed/",
        "https://www.sciencedaily.com/rss/top/science.xml",
        "https://feeds.arstechnica.com/arstechnica/science"
    ]
}
```

- Add new categories or modify existing ones.
- If a single feed is temporarily unreachable, Bubble News logs a warning and continues processing remaining feeds smoothly.

---

## Security and Privacy

- **Safe Generic Defaults**: All configuration values in the repository use generic placeholders.
- **Zero Telemetry**: Bubble News connects only to configured RSS feeds/article websites, the Google Gemini API, and your Disroot SMTP server.
- **Single Email Address**: The same configured Disroot address is used as both the sender (`From:`) and receiver (`To:`).

---

## Troubleshooting

- **Logs**: Execution timestamps, warnings, and error traces are saved in `bubble_news.log`.
- **Missing Articles**: If an RSS feed lacks publication timestamps, Bubble News attempts to extract the date from article metadata. If no articles were published within the 12-hour window, Bubble News delivers an alert email indicating no new stories were found.
- **Gemini API Key**: Obtain a free API key at [Google AI Studio](https://aistudio.google.com).
