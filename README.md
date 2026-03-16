# SpotMe

AI-powered workout tracker with Whoop integration. Claude is your coach.

## What it does

- Builds and adapts your training program based on Whoop biometrics
- Voice input — talk to log sets and get coaching
- Video form checks — record your lifts, get AI analysis
- Auto-syncs workouts to Whoop (no more manual entry)
- Dynamic UI that adapts based on your recovery, program phase, and behavior

## Setup

### Requirements
- Python 3.11+
- Node.js 20+
- ffmpeg
- A Claude API key
- A Whoop account + developer app

### Install

```bash
git clone https://github.com/jd1207/spotme.git
cd spotme

# backend
pip install -e ".[dev]"
cp .env.example .env
# edit .env with your keys

# frontend
cd frontend && npm install && npm run build && cd ..

# run
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Open `http://your-steam-deck-ip:8000` on your phone.

### Deploy on Steam Deck

```bash
cp deploy/spotme.service ~/.config/systemd/user/
cp deploy/spotme-whoop-sync.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now spotme
systemctl --user enable --now spotme-whoop-sync.timer
```

## Architecture

```
Phone (PWA) <---> Local Server (Steam Deck) <---> Claude API
                        |
                        +--> Whoop API (read biometrics, write workouts)
                        +--> SQLite (workout history, program state)
```

- **Frontend:** React + Vite PWA with dynamic Claude-driven layouts
- **Backend:** Python FastAPI + SQLite
- **AI:** Claude for coaching, programming, and form analysis
- **Whoop:** Full biometric read + workout write via [whoop-write-api](https://github.com/jd1207/whoop-write-api)

## License

MIT
