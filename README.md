# Morning Market Analyst — Telegram Bot

Sends a daily AI-generated options briefing to your Telegram every weekday morning.
Also responds to `/analyze` for on-demand runs.

---

## Step 1 — Create Your Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g. `Market Analyst`) and username (e.g. `my_market_bot`)
4. BotFather gives you a **token** — save it

---

## Step 2 — Get Your Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an API key under **API Keys**
3. Make sure your account has credits loaded

---

## Step 3 — Deploy to Your VPS

```bash
# SSH into your server
ssh ubuntu@your-server-ip

# Clone / copy the project
git clone <your-repo> market-bot   # or scp the folder
cd market-bot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 4 — Configure Environment

```bash
cp .env.example .env
nano .env
```

Fill in:
```
TELEGRAM_TOKEN=<from BotFather>
ANTHROPIC_API_KEY=<from Anthropic console>
CHAT_ID=<see Step 5>
BRIEF_HOUR=6
BRIEF_MINUTE=30
TIMEZONE=America/Los_Angeles
```

---

## Step 5 — Find Your Chat ID

```bash
# Start your bot in Telegram (search for it, tap Start, send any message)
# Then run:
python get_chat_id.py
```

Copy the Chat ID into your `.env` as `CHAT_ID`.

---

## Step 6 — Test It

```bash
# Activate venv if not already
source venv/bin/activate

# Quick test — run analysis once
python -c "
import asyncio
from analyst import run_morning_analysis
result = asyncio.run(run_morning_analysis())
print(result[:500])
"
```

---

## Step 7 — Run as a System Service (auto-start on reboot)

```bash
# Copy the service file
sudo cp market-bot.service /etc/systemd/system/

# Edit paths if your username isn't 'ubuntu'
sudo nano /etc/systemd/system/market-bot.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable market-bot
sudo systemctl start market-bot

# Check it's running
sudo systemctl status market-bot

# View logs live
sudo journalctl -u market-bot -f
```

---

## Telegram Commands

| Command | Action |
|---|---|
| `/analyze` | Run a full briefing right now |
| `/status` | Show bot status + next scheduled time |
| `/help` | List commands |

---

## Changing the Schedule

Edit `.env`:
```
BRIEF_HOUR=7       # 7 AM
BRIEF_MINUTE=0     # :00
TIMEZONE=America/New_York
```

Then restart the service:
```bash
sudo systemctl restart market-bot
```

---

## Recommended VPS

Any $5–6/month VPS works:
- **DigitalOcean** Droplet (Ubuntu 22.04, 1GB RAM)
- **Vultr** Cloud Compute
- **Linode** Nanode

The bot uses ~50MB RAM and almost no CPU when idle.

---

## File Structure

```
market-bot/
├── bot.py              # Telegram bot + scheduler
├── analyst.py          # Claude API call with web search
├── get_chat_id.py      # One-time helper to find your chat ID
├── requirements.txt    # Python dependencies
├── .env.example        # Config template
├── .env                # Your actual config (never commit this)
└── market-bot.service  # Systemd service file
```
