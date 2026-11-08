# AI Job Search & Live Dashboard Platform

An autonomous, intelligent AI agent that continuously searches for **Software Engineer**, **Associate Software Engineer**, and early-career tech positions across **LinkedIn Jobs, LinkedIn Posts, TopJobs.lk, ITPro.lk, Rooster.jobs, and Xpress.jobs**, analyzes every opportunity against your candidate profile using **Google Gemini AI**, and automatically updates an interactive **Live Web & Mobile Dashboard** hosted on **GitHub Pages**.

---

## 🌟 Key Highlights & Engineering Features

- **Multi-Portal Ingestion (6 Sources)**: Scrapes and indexes tech openings from:
  - 💼 **LinkedIn Jobs** (Public Guest API, no login required)
  - 📰 **LinkedIn Public Posts** (Shared hiring posts by recruiters & engineering leads)
  - 🇱🇰 **TopJobs.lk** (Software Development & QA functional area)
  - 💻 **ITPro.lk** (Sri Lanka's dedicated IT job portal)
  - 🐓 **Rooster.jobs** (Direct REST API integration)
  - ⚡ **Xpress.jobs** (Dynamic sitemap feed ingestion)
- **Safe, Ban-Free Extraction**: Requires **no user account logins or cookies**, completely eliminating any risk of personal account restrictions.
- **Failover / Hybrid Extraction**: Automatically falls back to managed third-party APIs (RapidAPI JSearch) if LinkedIn guest endpoints encounter burst rate-limiting.
- **Intelligent Pre-Filtering & Location Rules**: 
  - Sri Lanka roles: Accepts On-site, Hybrid, and Remote (with city filters for Colombo, Jaffna, Kandy, Galle, Kurunegala, and Gampaha).
  - International roles: Accepts **strictly 100% Remote** only (rejects international roles requiring relocation).
- **Google Gemini Semantic Scoring**: Evaluates candidate fit against your CV, analyzes tech stack alignment (C#/.NET, Java/Spring Boot, React/TypeScript), detects missing skills, and formats concise recruiter-fit rationales.
- **Interactive Live Dashboard**: PWA-ready dashboard with live search, filters, table/card views, deep-dive modal inspection, and personal tracking (Bookmarked, Applied, Omitted).
- **24/7 Automated Scheduling & GitHub Pages Hosting**: Serverless runner on GitHub Actions every 3 hours that updates the dataset and deploys the live site to **GitHub Pages** (`https://abivarsan.github.io/AI-Job-Search-Agent/`) for $0 forever!

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
├── pipeline.py                # Multi-portal orchestration pipeline
├── scheduler.py               # Background daemon using APScheduler
├── main.py                    # Command-line interface with rich output
├── DEPLOYMENT.md              # 24/7 Cloud deployment & GitHub Pages guide
├── .github/workflows/
│   └── job_search_sweep.yml   # 3-Hour automated serverless runner & Pages deployer
├── extractors/
│   ├── base.py                # BaseJobExtractor interface & JobItem model
│   ├── linkedin_guest.py      # Unauthenticated LinkedIn public search extractor
│   ├── linkedin_posts.py      # Public feed post extractor with snowflake gate
│   ├── topjobs_lk.py          # TopJobs.lk IT/Software extractor
│   ├── itpro_lk.py            # ITPro.lk software engineering extractor
│   ├── rooster_jobs.py        # Rooster.jobs REST API extractor
│   ├── xpress_jobs.py         # Xpress.jobs sitemap feed extractor
│   └── rapidapi_jsearch.py    # Fallback aggregator extractor
├── filters/
│   ├── heuristic_filter.py    # Negative seniority & location rules
│   └── ai_evaluator.py        # Gemini AI semantic fit scoring engine
├── dashboard/
│   ├── app.py                 # FastAPI local desktop server
│   └── exporter.py            # SQLite to static web JSON exporter
└── web/
    ├── index.html             # Responsive desktop/mobile UI
    ├── app.js                 # Client-side filtering & status logic
    ├── sw.js                  # PWA offline cache service worker
    ├── manifest.json          # PWA metadata
    └── data/
        └── jobs.json          # Live exported job listings & AI evaluations
```

---

## ☁️ 24/7 Cloud Hosting via GitHub Pages (100% Free)

You can run this agent completely online for free using **GitHub Actions & GitHub Pages**. It will run every **3 hours**, evaluate jobs with Gemini AI, and update your live dashboard.

👉 **See the complete setup in [DEPLOYMENT.md](DEPLOYMENT.md).**

---

## 🚀 Quickstart Guide

### 1. Configure Your Environment

Copy `.env.example` to `.env`:

```bash
copy .env.example .env
```

Open `.env` and fill in your Gemini API key:

```ini
# Google Gemini API key (https://aistudio.google.com/)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
MIN_MATCH_SCORE=70
```

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
    "C#", ".NET", "Java", "Spring Boot", "React", "TypeScript", "SQL"
  ],
  "target_locations": ["Sri Lanka", "Remote"]
}
```

---

## 🛠️ Running the Application

### Launch Local Dashboard
Starts the FastAPI local server with direct SQLite access and opens the dashboard in your default browser:

```bash
python main.py --dashboard
```

### Run a Single Search Immediately
Executes an immediate search across configured keywords, evaluates newly discovered jobs, saves them to SQLite, and updates the local dataset:

```bash
python main.py --run-once
```

### Export Dataset for Web
Exports SQLite records to `web/data/jobs.json` for GitHub Pages / Vercel:

```bash
python main.py --export-web
```

### View High-Match Jobs Table
Shows all top-matching jobs recorded in the database:

```bash
python main.py --list-matches
```

### View Pipeline Statistics
Shows total indexed jobs, AI evaluations, and portal breakdown:

```bash
python main.py --stats
```

---

## 🛡️ LinkedIn Terms of Service & Technical Safety

1. **Unauthenticated Public Endpoints**: This agent does **not** log in to your personal LinkedIn account. It queries public job search endpoints, guaranteeing that your personal profile can never be flagged or restricted.
2. **Polite Request Throttling**: The scraper incorporates randomized jitter delays (2.5 to 4 seconds) between requests to prevent triggering rate-limit firewalls.
3. **Graceful Failover**: If LinkedIn responds with HTTP 429 (Too Many Requests), the pipeline automatically switches to the secondary search API (JSearch) or pauses until the next scheduled sweep.
