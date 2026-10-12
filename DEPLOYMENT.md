# 24/7 Cloud Deployment Guide (GitHub Actions)

This guide walks you through deploying your AI Job Search Agent to run **24/7 online for free** using **GitHub Actions**.

Once deployed, GitHub's cloud servers will run the agent every **3 hours**, scan LinkedIn for newly posted Software Engineer & Associate roles, evaluate them with Gemini AI, and send instant alerts to your **Telegram** or **WhatsApp**—even when your computer is completely turned off.

---

## 📋 Required API Keys (100% Free)

You only need **2 free keys**:

### 1. `GEMINI_API_KEY` (Google Gemini AI)
1. Go to **[Google AI Studio](https://aistudio.google.com/)**.
2. Sign in with your Google account.
3. Click **"Get API key"** -> **"Create API key in new project"**.
4. Copy the generated key (starts with `AIzaSy...`).

---

### 2. Telegram Bot Credentials (No SMS verification, works in all regions)

1. Open **Telegram** on your mobile phone or desktop.
2. Search for **`@BotFather`** (the official bot with the blue checkmark) and press **Start**.
3. Send the command: `/newbot`
4. Enter a name for your bot, e.g.: `JobSearchBot`
5. Enter a username ending in `bot`, e.g.: `abivarsan_jobs_bot`
6. BotFather will reply with your **Bot Token**:
   * Example: `789123456:AAFlk...`
   * 👉 **This is your `TELEGRAM_BOT_TOKEN`**.
7. Now search for **`@userinfobot`** on Telegram, press **Start**:
   * It will display your numeric user ID (e.g., `123456789`).
   * 👉 **This is your `TELEGRAM_CHAT_ID`**.
8. Open your newly created bot in Telegram and press **Start** (so it has permission to message you).

---

## 🚀 Step 1: Create a Private GitHub Repository

1. Go to [github.com/new](https://github.com/new).
2. Enter repository name: `AI-Job-Search-Agent`.
3. Choose **Private**.
4. Click **Create repository**.

---

## 💻 Step 2: Push Your Code to GitHub

Open PowerShell in your project folder (`c:\Users\kethe\Documents\AI Agent\Agent 01`) and run:

```powershell
git add .
git commit -m "feat: add telegram support and 3-hour cloud workflow"
git push -u origin main
```

---

## 🔐 Step 3: Add Your Secrets in GitHub

1. Open your repository on GitHub.
2. Click **Settings** (top navigation tab).
3. In the left sidebar, click **Secrets and variables** -> **Actions**.
4. Click **New repository secret** and add:

| Secret Name | Value | Required? |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Your key from Google AI Studio | **Yes** |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather | **Yes (Recommended)** |
| `TELEGRAM_CHAT_ID` | Numeric ID from @userinfobot | **Yes (Recommended)** |
| `TWILIO_ACCOUNT_SID` | (Optional) Twilio Account SID | Optional |
| `TWILIO_AUTH_TOKEN` | (Optional) Twilio Auth Token | Optional |
| `TWILIO_WHATSAPP_FROM` | (Optional) `whatsapp:+14155238886` | Optional |
| `WHATSAPP_TO` | (Optional) Your WhatsApp phone | Optional |

---

## 🧪 Step 4: Test Your First Run (One-Click)

1. In your GitHub repository, click on the **Actions** tab.
2. In the left sidebar, click **AI Job Search 3-Hour Agent**.
3. Click the **Run workflow** dropdown on the right.
4. Check the box **"Send test Telegram ping only"** and click **Run workflow**.
5. Within 45 seconds, your Telegram bot will ping you:
   > 🤖 *AI Job Search Agent Connected!*

---

## ⏰ Step 5: Automated 3-Hour Schedule

Once verified:
* Click **Run workflow** again with both test checkboxes **unchecked** to run your first real job search sweep.
* From then on, GitHub Actions runs automatically every **3 hours** (`0 */3 * * *` at 00:00, 03:00, 06:00, 09:00, 12:00, 15:00, 18:00, 21:00 UTC).
* You can view past runs, execution times, and logs anytime in the **Actions** tab.

---

## 📱 Step 6: Connect Web & Mobile Dashboard (Vercel - 100% Free & Private)

You can view all extracted jobs anytime from your smartphone, tablet, or laptop via your private Vercel deployment:

### 1. Connect to Vercel (2 Minutes)
1. Go to **[vercel.com](https://vercel.com/)** and sign in with your GitHub account.
2. Click **"Add New..."** -> **"Project"**.
3. Select your private repository: **`Abivarsan/AI-Job-Search-Agent`** and click **Import**.
4. In the Project Configuration:
   - Framework Preset: **Other**
   - Root Directory: `./` (or leave default)
   - Output Directory: `web`
5. Click **Deploy**.
6. Within 15 seconds, your personal dashboard URL will be live (e.g. `https://ai-job-search-agent.vercel.app`)!

### 2. Install on Mobile Phone (Offline PWA)
- **iPhone / Safari**: Open your Vercel link -> Tap **Share** icon -> Tap **"Add to Home Screen"**.
- **Android / Chrome**: Open your Vercel link -> Tap menu (**⋮**) -> Tap **"Install app"** or **"Add to Home screen"**.
- The app icon will appear on your phone screen and works **100% offline** even when you have no internet connection!

### 3. Local Desktop Dashboard (Offline & Direct SQLite Access)
To view and manage jobs locally on your computer with full status tracking:
```powershell
python main.py --dashboard
```
This automatically launches the interactive dashboard at **`http://localhost:8000`** with live search, filters, bookmarker, and application notes.

