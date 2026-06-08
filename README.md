# Auto Forex MT5 Bot

Fully automated Python 3.10+ MT5 demo-account bot for EURUSD, GBPUSD, and XAUUSD using:

- H4 trend bias from EMA 50/200.
- M15 SMC-style order block / fair value gap detection.
- Fibonacci retracement confluence in the 0.5 to 0.618 golden zone.
- Strict 1% balance risk per trade and 1:2 RR.
- MT5-aware lot sizing via `order_calc_profit`, with tick-size/tick-value fallback for Forex and metals.
- London/New York overlap session filter.
- Forex Factory high-impact USD/EUR/GBP news pause, 30 minutes before and after events.
- Rotating log file at `logs/auto_forex.log`.

## Important MT5/Linux Note

The Python `MetaTrader5` package talks to a locally running MT5 terminal. On a Linux VPS, that normally means running the Windows MT5 terminal under Wine, often with `xvfb`, or using a Windows VPS. The bot code is Linux-service ready, but the MT5 terminal must be installed, logged into the demo account, and visible to the Python package on the same machine.

## Local Install

```bash
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
```

Set these values in `.env`:

```bash
MT5_LOGIN=your_demo_login
MT5_PASSWORD=your_demo_password
MT5_SERVER=your_broker_demo_server
MT5_PATH=/path/to/terminal64.exe
BOT_SYMBOLS=EURUSD,GBPUSD,XAUUSD
```

Broker symbol names can differ. If your broker uses suffixes, set for example:

```bash
BOT_SYMBOLS=EURUSDm,GBPUSDm,XAUUSDm
```

## Run Manually

```bash
source .venv/bin/activate
python -m forex_bot.main
```

## Deploy On Ubuntu VPS

```bash
sudo apt update
sudo apt install -y python3.10 python3.10-venv python3-pip git curl
git clone <your-repo-url> /home/ubuntu/auto_forex
cd /home/ubuntu/auto_forex
python3.10 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
```

### MT5 Under Wine

Install Wine and a virtual display:

```bash
sudo dpkg --add-architecture i386
sudo apt update
sudo apt install -y wine64 wine32 xvfb winbind
```

Install MT5 from your broker:

```bash
mkdir -p ~/mt5
cd ~/mt5
wget -O mt5setup.exe "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
xvfb-run -a wine mt5setup.exe
```

Start MT5 and log into the demo account once:

```bash
xvfb-run -a wine ~/.wine/drive_c/Program\ Files/MetaTrader\ 5/terminal64.exe
```

Then set `MT5_PATH` in `.env` to that terminal path. Keep in mind that exact Wine paths can vary depending on broker installer and Wine prefix.

## Systemd

```bash
sudo cp systemd/auto-forex.service /etc/systemd/system/auto-forex.service
sudo systemctl daemon-reload
sudo systemctl enable auto-forex
sudo systemctl start auto-forex
sudo systemctl status auto-forex
journalctl -u auto-forex -f
```

## PM2 Alternative

```bash
sudo npm install -g pm2
pm2 start ecosystem.config.js
pm2 save
pm2 startup systemd
pm2 logs auto-forex
```

## Git Workflow

After every bot change on the VPS:

```bash
git status
git add .
git commit -m "Update auto forex bot"
git pull --rebase
git push
```

If changes are made locally first:

```bash
git add .
git commit -m "Update auto forex bot"
git push
ssh ubuntu@<vps-ip>
cd /home/ubuntu/auto_forex
git pull --rebase
sudo systemctl restart auto-forex
```

## Strategy Settings

Key `.env` options:

```bash
BOT_RISK_PER_TRADE=0.01
BOT_RR_RATIO=2.0
BOT_SESSION_WINDOWS_UTC=12:00-16:00
BOT_NEWS_PAUSE_MINUTES=30
BOT_MIN_ZONE_OVERLAP=0.6
BOT_XAUUSD_ATR_SL_BUFFER_MULTIPLIER=0.35
BOT_XAUUSD_MAX_SPREAD_POINTS=400
```

## Backtesting And Safety

Run this on demo first. SMC order blocks and FVGs are discretionary concepts, so this implementation uses deterministic rules that should be forward-tested and tuned per broker feed before any live account use.
