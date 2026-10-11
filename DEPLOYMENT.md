# 24/7 Cloud Deployment Guide (GitHub Actions)

This guide walks you through deploying your AI Job Search Agent to run **24/7 online for free** using **GitHub Actions**.

Once deployed, GitHub's cloud servers will run the agent every **3 hours**, scan LinkedIn for newly posted Software Engineer & Associate roles, evaluate them with Gemini AI, and send instant alerts to your WhatsApp—even when your computer is completely turned off.

---

## 📋 Prerequisites

Before deploying, ensure you have:
1. A [GitHub account](https://github.com/).
2. A free [Google Gemini API Key](https://aistudio.google.com/).
3. A free [Twilio account](https://www.twilio.com/) with WhatsApp sandbox setup.

---

## 🚀 Step 1: Create a Private GitHub Repository

1. Go to [github.com/new](https://github.com/new).
2. Enter a repository name, e.g., `ai-job-search-agent`.
3. Select **Private** (recommended, so your candidate profile remains confidential).
4. Do **not** check "Add a README file" or ".gitignore" (we already have them).
5. Click **Create repository**.

---

## 💻 Step 2: Push Your Code to GitHub

Open PowerShell in your project folder (`c:\Users\kethe\Documents\AI Agent\Agent 01`) and run:

```powershell
# 1. Initialize git
git init -b main

# 2. Stage all project files (.env is automatically ignored for safety)
git add .

# 3. Commit the project
git commit -m "feat: complete AI Job Search Agent with 3-hour GitHub Actions cloud workflow"

# 4. Link your GitHub repository (replace YOUR_USERNAME and YOUR_REPO)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# 5. Push to GitHub
git push -u origin main
```

---

## 🔐 Step 3: Add Your Secrets in GitHub

To allow the cloud runner to use Gemini and Twilio without committing API keys to code:

1. Open your repository on GitHub.
2. Go to **Settings** (top navigation tab).
3. In the left sidebar, click **Secrets and variables** -> **Actions**.
4. Click **New repository secret** and add the following:

| Secret Name | Value | Required? |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Your Google Gemini API key from Google AI Studio | **Yes** |
| `TWILIO_ACCOUNT_SID` | Your Twilio Account SID (found on your Twilio Console) | **Yes** |
| `TWILIO_AUTH_TOKEN` | Your Twilio Auth Token (found on your Twilio Console) | **Yes** |
| `TWILIO_WHATSAPP_FROM` | Twilio sandbox number (usually `whatsapp:+14155238886`) | **Yes** |
| `WHATSAPP_TO` | Your mobile number with country code (e.g. `whatsapp:+1234567890`) | **Yes** |
| `RAPIDAPI_KEY` | Optional RapidAPI JSearch key for backup scraping | Optional |

---

## 🧪 Step 4: Test Your First Run (One-Click)

Before waiting for the 3-hour timer, verify everything works:

1. In your GitHub repository, click on the **Actions** tab.
2. In the left sidebar, click **AI Job Search 3-Hour Agent**.
3. Click the **Run workflow** dropdown on the right.
4. Check the box **"Send test WhatsApp ping only"** and click **Run workflow**.
5. Within 45–60 seconds, check your WhatsApp! You will receive a confirmation ping:
   > 🤖 *AI Job Search Agent Connected!*

---

## ⏰ Step 5: Automatic 3-Hour Schedule

Once verified:
* Click **Run workflow** again with the test checkbox **unchecked** to run your first real job search sweep.
* From then on, GitHub Actions will automatically run every **3 hours** (`0 */3 * * *` at 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 UTC).
* You can view past runs, execution times, and logs anytime in the **Actions** tab.

---

## 🛡️ How Deduplication Works in the Cloud

* Each run restores `jobs.db` from GitHub Actions cache (`actions/cache@v4`).
* Only brand-new job listings posted since the last run are evaluated and alerted.
* After every run, the updated database is backed up as a 90-day downloadable artifact (`jobs-database-backup`).
