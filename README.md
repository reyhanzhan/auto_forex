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

The Python `MetaTrader5` package talks to a locally running MT5 terminal and is distributed as a Windows Python package. On a Linux VPS, do not run the bot with native Linux Python. Use one of these paths:

- Recommended for simplicity: use a Windows VPS and run `python -m forex_bot.main` beside the MT5 terminal.
- Linux VPS path: run Windows Python, MT5 terminal, and the `MetaTrader5` package under Wine/Xvfb.

The native Linux `systemd/auto-forex.service` is useful only if your environment provides a compatible MT5 bridge. For normal Ubuntu + Wine deployment, use `systemd/auto-forex-wine.service`.

## Local Install On Windows

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

On Windows PowerShell, use:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
```

## Run Manually On Windows

```bash
source .venv/bin/activate
python -m forex_bot.main
```

## Deploy On Ubuntu VPS With Wine

```bash
sudo apt update
sudo apt install -y git curl wget xvfb wine64 winbind cabextract
git clone <your-repo-url> /home/ubuntu/auto_forex
cd /home/ubuntu/auto_forex
cp .env.example .env
nano .env
```

Install Windows Python 3.10 under Wine:

```bash
mkdir -p ~/installers
cd ~/installers
wget -O python-3.10.11-amd64.exe https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe
xvfb-run -a wine python-3.10.11-amd64.exe /quiet InstallAllUsers=1 PrependPath=1 TargetDir=C:\\Python310 Include_pip=1
cd /home/ubuntu/auto_forex
xvfb-run -a wine C:\\Python310\\python.exe -m pip install --upgrade pip
xvfb-run -a wine C:\\Python310\\python.exe -m pip install -r requirements.txt
```

Install MT5 from your broker or MetaQuotes:

```bash
mkdir -p ~/mt5
cd ~/mt5
wget -O mt5setup.exe "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
xvfb-run -a wine mt5setup.exe
```

Start MT5 and log into the demo account once. This may require VNC or another desktop session if your broker installer needs GUI interaction:

```bash
xvfb-run -a wine ~/.wine/drive_c/Program\ Files/MetaTrader\ 5/terminal64.exe
```

Then set `MT5_PATH` in `.env` to that terminal path. Keep in mind that exact Wine paths can vary depending on broker installer and Wine prefix.

Test import and connection bootstrap:

```bash
cd /home/ubuntu/auto_forex
xvfb-run -a wine C:\\Python310\\python.exe -c "import MetaTrader5 as mt5; print(mt5.__version__)"
xvfb-run -a wine C:\\Python310\\python.exe -m forex_bot.main
```

## Systemd On Ubuntu + Wine

```bash
sudo cp systemd/auto-forex-wine.service /etc/systemd/system/auto-forex.service
sudo systemctl daemon-reload
sudo systemctl enable auto-forex
sudo systemctl start auto-forex
sudo systemctl status auto-forex
journalctl -u auto-forex -f
```

## PM2 Alternative

```bash
sudo npm install -g pm2
chmod +x scripts/run_wine_bot.sh
pm2 start ecosystem.config.js --only auto-forex
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
