# 24/7 Cloud Deployment & GitHub Pages Hosting Guide

This guide walks you through deploying your AI Job Search Agent to run **24/7 online for free** using **GitHub Actions** and hosting your interactive web dashboard directly on **GitHub Pages**.

Once deployed:
1. GitHub's cloud servers run the agent every **3 hours** (`0 */3 * * *`).
2. It extracts software engineering roles across **LinkedIn Jobs, LinkedIn Posts, TopJobs.lk, ITPro.lk, Rooster.jobs, and Xpress.jobs**.
3. It evaluates opportunities with **Google Gemini AI** against your candidate profile.
4. It automatically exports the refreshed dataset to `web/data/jobs.json`.
5. It commits the changes and deploys the dashboard directly to **GitHub Pages** (`https://abivarsan.github.io/AI-Job-Search-Agent/`)—all with zero manual intervention!

---

## 📋 Required API Key (100% Free)

You only need **1 free key**:

### `GEMINI_API_KEY` (Google Gemini AI)
1. Go to **[Google AI Studio](https://aistudio.google.com/)**.
2. Sign in with your Google account.
3. Click **"Get API key"** -> **"Create API key in new project"**.
4. Copy the generated key (starts with `AIzaSy...`).

*(No Telegram bot, WhatsApp, or Twilio tokens are required for V1!)*

---

## 🚀 Step 1: Set Repository to Public & Enable GitHub Pages

### 1. Make Repository Public
*(Public repositories receive **unlimited free GitHub Actions minutes** and **free GitHub Pages hosting**)*
1. Go to your repository on GitHub: `https://github.com/Abivarsan/AI-Job-Search-Agent`.
2. Click **Settings** (top menu bar).
3. Scroll down to the **Danger Zone** at the bottom.
4. Under **Change repository visibility**, click **Change visibility** -> choose **Make public**.

### 2. Enable GitHub Pages Deployment
1. Still in repository **Settings**, click **Pages** in the left sidebar.
2. Under **Build and deployment** -> **Source**:
3. Select **GitHub Actions**.
4. That's it! GitHub Pages will now automatically receive builds from your 3-hour workflow.

---

## 🔐 Step 2: Add Your Gemini API Key in GitHub Secrets

1. In repository **Settings**, go to **Secrets and variables** -> **Actions** (left sidebar).
2. Click **New repository secret**.
3. Add:
   - **Name**: `GEMINI_API_KEY`
   - **Secret**: Your key from Google AI Studio.
4. Click **Add secret**.

---

## 🧪 Step 3: Trigger Your First Automated Run

1. Go to the **Actions** tab in your repository.
2. In the left sidebar, click **AI Job Search 3-Hour Agent & Dashboard Sync**.
3. Click the **Run workflow** dropdown on the right -> Click the green **Run workflow** button.
4. The workflow will:
   - Run multi-portal extraction & Gemini AI scoring.
   - Sync `jobs.db` and export `web/data/jobs.json`.
   - Automatically deploy to GitHub Pages!
5. Once complete, visit your live dashboard at:
   **`https://abivarsan.github.io/AI-Job-Search-Agent/`**

---

## 📱 Alternative / Dual Hosting: Vercel

If you also wish to keep Vercel active alongside GitHub Pages:
1. Go to your project on **[vercel.com](https://vercel.com/)**.
2. Go to **Settings** -> **Git**.
3. Set **Production Branch** to `V1`.
4. Click **Save**. Vercel will automatically redeploy whenever `V1` receives updates!

---

## 💻 Local Desktop Dashboard (Offline & Direct SQLite Access)

To run and manage jobs locally on your computer with full status tracking:
```powershell
python main.py --dashboard
```
This launches the interactive dashboard at **`http://localhost:8000`** with live search, filters, bookmarker, omit tab, and application notes.
