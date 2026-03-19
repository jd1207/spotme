# SpotMe

AI-powered workout tracker with Whoop integration. Claude is your coach.

Self-hosted PWA — runs on any machine, open on your phone at the gym.

## What it does

- AI coaching that learns your program, adapts to recovery, and remembers your history
- Voice input — talk to log sets and get coaching between sets
- Whoop integration — reads biometrics, auto-syncs workouts, tracks journal signals
- Video form checks — record your lifts, get AI analysis
- Meal tracking with macro estimation and Whoop journal sync
- Dynamic UI that adapts based on your recovery, program phase, and behavior

## How it works

```
Your phone (PWA) <---> Your server <---> Claude (via Claude Code CLI)
                           |
                           +--> Whoop API (optional, read + write)
                           +--> SQLite (all your data, local)
```

The server runs on any always-on machine — old laptop, Raspberry Pi, NAS, Steam Deck.
Your phone connects over local network or Tailscale. All data stays on your hardware.

## Quick start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (recommended) or Python 3.11+ and Node.js 20+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and logged in

Claude Code provides the AI — no API key needed. Just install it and log in:

```bash
npm install -g @anthropic-ai/claude-code
claude  # follow the login prompts, then exit
```

### Docker (recommended)

```bash
git clone https://github.com/jd1207/spotme.git
cd spotme
docker compose up -d
```

That's it. Open `http://<your-server-ip>:8000` on your phone.

Your data lives in a Docker volume. Claude Code credentials are mounted read-only from your host.

### Manual install

```bash
git clone https://github.com/jd1207/spotme.git
cd spotme

# backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install -e ".[whoop]"   # optional: whoop integration
cp .env.example .env

# frontend
cd frontend && npm install && npm run build && cd ..

# run
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Open `http://<your-server-ip>:8000` on your phone. Add to home screen for the full PWA experience.

### First launch

1. Swipe through the intro slides
2. Fill out the intake — name, experience, goals, equipment, frequency
3. Optionally paste your training plan (or let Claude create one)
4. Start chatting — tell Claude what you're working on today

### Connect Whoop (optional)

Go to Profile tab > Connect Whoop. Log in with your Whoop email and password.
This uses [whoop-write-api](https://github.com/jd1207/whoop-write-api) (Cognito auth, reverse-engineered).
Once connected, Claude can read your recovery data and auto-sync workouts.

### Run as a service (Linux)

For always-on hosting:

```bash
cp deploy/spotme.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now spotme
```

Optional timers for auto-sync and morning briefings:

```bash
cp deploy/spotme-whoop-sync.* ~/.config/systemd/user/
cp deploy/spotme-morning.* ~/.config/systemd/user/
systemctl --user enable --now spotme-whoop-sync.timer
systemctl --user enable --now spotme-morning.timer
```

### Access from anywhere

Use [Tailscale](https://tailscale.com/) to access your server from any network.
Install on your server and phone, then use the Tailscale IP instead of your local IP.

## Architecture

- **Frontend:** React + TypeScript + Vite PWA with offline support
- **Backend:** Python FastAPI + SQLite (WAL mode for concurrency)
- **AI:** Claude via Claude Code CLI subprocess (uses your Claude Code login, no API key)
- **Whoop:** Read biometrics + write workouts/journal via [whoop-write-api](https://github.com/jd1207/whoop-write-api) (Cognito auth, no OAuth app needed)

## Development

```bash
# backend tests
pytest -x --tb=short

# frontend dev server (hot reload)
cd frontend && npm run dev

# backend dev server
uvicorn server.main:app --host 0.0.0.0 --port 8000 --reload
```

## Roadmap

### Now
- [ ] Improve onboarding flow for new users
- [ ] Whoop connection during onboarding instead of buried in profile

### Next
- [ ] Multi-user support (separate profiles on shared server)
- [ ] iOS app via Capacitor (native push notifications, HealthKit)
- [ ] Push notifications for morning briefing and workout reminders
- [ ] Docker image for easier deployment

### Later
- [ ] Apple Watch companion (quick set logging, recovery glance)
- [ ] Program builder UI (currently text-based via Claude)
- [ ] Export/import training data
- [ ] Cloud hosting option

## License

MIT
