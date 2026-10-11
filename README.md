# AI Job Search & Notification Agent

An automated, intelligent AI agent that continuously searches for **Software Engineer**, **Associate Software Engineer**, and early-career tech positions on LinkedIn, analyzes every opportunity against your personal profile using **Google Gemini AI**, and delivers real-time job alerts directly to your **WhatsApp** (or Telegram).

---

## 🌟 Key Highlights & Engineering Features

- **Safe, Ban-Free Extraction**: Uses LinkedIn's public guest search API (`/jobs-guest/jobs/api/seeMoreJobPostings/search`). **No login required**, completely eliminating any risk of personal account restrictions.
- **Failover / Hybrid Extraction**: Automatically falls back to managed third-party APIs (RapidAPI JSearch) if guest endpoints encounter burst rate-limiting.
- **Intelligent Pre-Filtering**: Deterministic heuristic rules instantly filter out senior, lead, staff, or executive roles before calling the AI, minimizing latency and saving LLM costs.
- **Google Gemini Semantic Scoring**: Evaluates candidate fit, analyzes tech stack alignment, detects missing skills, and formats a concise 2-sentence rationale.
- **Robust Deduplication**: Tracks job IDs and content hashes in SQLite, ensuring you never receive duplicate notifications for reposted roles.
- **Multi-Channel Alerting**: Direct WhatsApp notifications via the Twilio API (with support for Twilio Sandbox) plus zero-friction Telegram Bot support.
- **Automated Scheduling**: In-process background scheduler (APScheduler) or standalone CLI commands.

---

## 📁 Project Architecture

```
Agent 01/
├── .env.example               # Environment variables template
├── .gitignore                 # Excludes secrets, databases, logs, and venvs
├── requirements.txt           # Python dependencies
├── candidate_profile.json     # Your skills, target roles, and preferences
├── config.py                  # Settings loader using python-dotenv
├── database.py                # SQLite schema and deduplication repository
├── pipeline.py                # Core end-to-end orchestration pipeline
├── scheduler.py               # Background daemon using APScheduler
├── main.py                    # Command-line interface with rich output
├── DEPLOYMENT.md              # 24/7 Cloud deployment guide (GitHub Actions)
├── .github/workflows/
│   └── job_search_sweep.yml   # 3-Hour automated serverless runner
├── extractors/
│   ├── base.py                # BaseJobExtractor interface & JobItem model
│   ├── linkedin_guest.py      # Unauthenticated LinkedIn public search extractor
│   └── rapidapi_jsearch.py    # Fallback aggregator extractor
├── filters/
│   ├── heuristic_filter.py    # Negative & positive title heuristics
│   └── ai_evaluator.py        # Gemini AI semantic fit scoring engine
└── notifiers/
    ├── base.py                # BaseNotifier interface
    ├── whatsapp_twilio.py     # Twilio WhatsApp dispatcher
    └── telegram_notifier.py   # Telegram Bot dispatcher
```

---

## ☁️ 24/7 Cloud Hosting (No Computer Required)

You can run this agent completely online for free using **GitHub Actions**. It will run every **3 hours**, evaluate jobs with Gemini AI, and dispatch alerts to your WhatsApp 24/7.

👉 **See the complete setup in [DEPLOYMENT.md](DEPLOYMENT.md).**

---

## 🚀 Quickstart Guide

### 1. Configure Your Environment

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Open `.env` and fill in your keys:

```ini
# Google Gemini API key (https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key

# Minimum AI match score (0-100) to trigger notification
MIN_MATCH_SCORE=75

# Twilio WhatsApp Credentials (https://www.twilio.com/)
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
WHATSAPP_TO=whatsapp:+12345678901   # Your personal mobile number with country code

# Search Keywords & Target Locations
SEARCH_KEYWORDS=Software Engineer, Associate Software Engineer, Junior Software Engineer
SEARCH_LOCATIONS=Remote, United States
```

> [!TIP]
> **Testing WhatsApp with Twilio Sandbox**:
> 1. Log in to [Twilio Console](https://console.twilio.com/) -> Messaging -> Try WhatsApp.
> 2. Send the sandbox join code (e.g. `join <your-code>`) from your personal WhatsApp to `+1 415 523 8886`.
> 3. Run `python main.py --test-whatsapp` to verify connection!

---

### 2. Customize Your Candidate Profile

Edit `candidate_profile.json` to reflect your specific skills and background:

```json
{
  "target_roles": [
    "Software Engineer",
    "Associate Software Engineer",
    "Junior Software Engineer"
  ],
  "experience_years": 1,
  "experience_level": "Entry / Associate (0-2 years)",
  "primary_skills": [
    "Python", "JavaScript", "TypeScript", "React", "FastAPI", "PostgreSQL", "Git", "Docker"
  ],
  "target_locations": ["Remote", "United States"]
}
```

---

## 🛠️ Running the Agent

### Run a Single Search Immediately
Executes an immediate search across configured keywords, evaluates found jobs, saves them to SQLite, and sends WhatsApp alerts for high matches:

```bash
python main.py --run-once
```

### Run in Background Daemon Mode
Runs continuously and triggers searches every `POLL_INTERVAL_MINUTES` (default: every 3 hours):

```bash
python main.py --daemon
```

### View High-Match Jobs Table
Shows all top-matching jobs recorded in the database:

```bash
python main.py --list-matches
```

### View Pipeline Statistics
Shows total indexed jobs, evaluations performed, and notifications sent:

```bash
python main.py --stats
```

### Verify WhatsApp Connectivity
Sends a test ping to verify that Twilio WhatsApp credentials are functioning:

```bash
python main.py --test-whatsapp
```

---

## 🛡️ LinkedIn Terms of Service & Technical Safety

1. **Unauthenticated Public Endpoints**: This agent does **not** log in to your personal LinkedIn account. It queries public job search endpoints, guaranteeing that your personal profile can never be flagged or restricted.
2. **Polite Request Throttling**: The scraper incorporates randomized jitter delays (2.5 to 4 seconds) between requests to prevent triggering rate-limit firewalls.
3. **Graceful Failover**: If LinkedIn responds with HTTP 429 (Too Many Requests), the pipeline automatically switches to the secondary search API (JSearch) or pauses until the next scheduled sweep.
