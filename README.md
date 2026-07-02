# Everpilot

> **Autopilot, not copilot, for your repositories.**

Everpilot is an autonomous code-maintenance system for GitHub. You delegate the ongoing care of a codebase to it and choose — per capability, per repository — whether it works fully autonomously or hands every change to a human for review.

## Capabilities

| | Capability | What it does |
|---|---|---|
| 🛡️ | **Security** | Continuously scans for vulnerabilities and lands fixes |
| 🎫 | **Issue Triage** | Reads new issues, classifies them, proposes and ships fixes |
| 📦 | **Dependencies** | Keeps third-party libraries current; absorbs Dependabot-style updates |
| 🧪 | **Test Hygiene** | Runs the test suite, diagnoses failures, opens fixes |
| ✨ | **Freshness** | General modernization so the codebase never rots |

Each capability is **independently toggleable** with three operating modes:

| Mode | Behaviour |
|---|---|
| **Autopilot** | Fully autonomous — no human in the loop |
| **Assisted** | Opens a PR and waits for your approval before merging |
| **Off** | Disabled |

## Project structure

```
everpilot/
├── backend/                 # Python 3.12 · FastAPI · uv
│   ├── src/everpilot/
│   │   ├── api/             # health, repos, webhooks routers
│   │   ├── models/          # Capability, RepoConfig Pydantic models
│   │   ├── config.py        # Pydantic Settings (env-driven)
│   │   └── main.py          # FastAPI application factory
│   ├── tests/
│   └── pyproject.toml
├── frontend/                # TypeScript · React 19 · Vite 8 · Tailwind 4
│   ├── src/
│   │   ├── components/      # Navbar, CapabilityToggle
│   │   ├── pages/           # LandingPage, DashboardPage, RepoDetailPage
│   │   ├── lib/api.ts       # Typed fetch client
│   │   └── types/           # Shared TypeScript types
│   └── package.json
├── amplify.yml              # AWS Amplify build config
└── .github/workflows/
    └── ci.yml               # Backend lint+test · Frontend build
```

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | ≥ 0.5 | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js](https://nodejs.org/) | ≥ 22 | [nodejs.org](https://nodejs.org/) or `brew install node` |
| [GitHub CLI](https://cli.github.com/) | any | `brew install gh` |

Python 3.12 is managed automatically by `uv` — no manual install needed.

## Setup

### 1. Clone

```bash
git clone https://github.com/silvexis/everpilot.git
cd everpilot
```

### 2. Backend

```bash
cd backend
cp .env.example .env
```

Open `.env` and fill in your GitHub App credentials (see [Creating a GitHub App](#creating-a-github-app) below).

```bash
uv sync --all-groups   # installs Python 3.12 + all dependencies
```

Start the API server:

```bash
uv run uvicorn everpilot.main:app --reload
```

The API is available at **<http://localhost:8000>**.
With `DEBUG=true` in your `.env`, interactive API docs are at <http://localhost:8000/docs>.

### 3. Frontend

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

The app is available at **<http://localhost:5173>**.
Vite proxies all `/api/*` requests to the backend, so no CORS setup is needed in development.

## Environment variables

All backend configuration is driven by environment variables (or a `backend/.env` file).

| Variable | Required | Description |
|---|---|---|
| `GITHUB_APP_ID` | Yes | Numeric App ID from your GitHub App settings |
| `GITHUB_APP_PRIVATE_KEY` | Yes | PEM-encoded private key (newlines as `\n`) |
| `GITHUB_WEBHOOK_SECRET` | Yes | Secret token used to verify webhook payloads |
| `GITHUB_CLIENT_ID` | Yes | OAuth client ID for user authorization |
| `GITHUB_CLIENT_SECRET` | Yes | OAuth client secret |
| `SECRET_KEY` | Yes | Random secret used for JWT signing — change in production |
| `APP_ENV` | No | `development` \| `production` (default: `development`) |
| `DEBUG` | No | `true` enables `/docs` and verbose logging (default: `false`) |
| `API_HOST` | No | Bind host (default: `0.0.0.0`) |
| `API_PORT` | No | Bind port (default: `8000`) |

## Creating a GitHub App

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**.
2. Set the **Webhook URL** to your public backend URL + `/api/v1/webhooks/github`.
3. Generate a **Webhook secret** and copy it into `GITHUB_WEBHOOK_SECRET`.
4. Set the following **Repository permissions**:
   - Contents: Read & write
   - Issues: Read & write
   - Pull requests: Read & write
   - Workflows: Read & write
5. Subscribe to events: `push`, `issues`, `pull_request`, `installation`, `installation_repositories`.
6. After creation, generate a **Private key** and download the `.pem` file.
7. Populate `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY` (contents of the `.pem`), `GITHUB_CLIENT_ID`, and `GITHUB_CLIENT_SECRET`.

## Development commands

### Backend

```bash
# Run tests with coverage report
uv run pytest

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Lint + format in one pass
uv run ruff check . --fix && uv run ruff format .
```

### Frontend

```bash
# Start dev server
npm run dev

# Production build
npm run build

# Lint
npm run lint

# Type check
npx tsc --noEmit

# Preview production build locally
npm run preview
```

## API reference

All routes are prefixed with `/api/v1`.

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness probe |
| `GET` | `/repos` | List installed repositories |
| `POST` | `/repos` | Install Everpilot on a repository |
| `GET` | `/repos/{owner}/{repo}` | Get capability config for a repo |
| `PATCH` | `/repos/{owner}/{repo}/capabilities` | Update a single capability's mode |
| `DELETE` | `/repos/{owner}/{repo}` | Uninstall Everpilot from a repo |
| `POST` | `/webhooks/github` | GitHub webhook receiver |

## Deployment

### Frontend — AWS Amplify

The frontend deploys automatically to AWS Amplify. The `amplify.yml` at the repo root configures the build:

```yaml
# amplify.yml (summary)
baseDirectory: frontend/dist
buildCommand: cd frontend && npm ci && npm run build
```

Custom domains are configured in the Amplify console:
- [everpilot.ai](https://everpilot.ai)
- [everpilot.dev](https://everpilot.dev)
- [everpilot.io](https://everpilot.io)

### Backend

The backend is a standard ASGI application. Deploy it to any platform that runs containers or Python processes (e.g. AWS ECS, Fly.io, Railway, Render):

```bash
# Production start command
uv run uvicorn everpilot.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Set `APP_ENV=production` and `DEBUG=false` in your production environment.

## CI / CD

GitHub Actions runs on every push and pull request to `main` and `develop`:

- **Backend job** — `ruff check`, `ruff format --check`, `pytest` (coverage ≥ 80%)
- **Frontend job** — `oxlint`, `tsc --noEmit`, `vite build`

## Contributing

1. Fork the repository.
2. Create a feature branch off `develop`: `git checkout -b feature/my-feature`.
3. Make your changes, add tests, and ensure CI passes locally.
4. Open a pull request targeting `develop`.

Bug reports and feature requests are welcome via [GitHub Issues](https://github.com/silvexis/everpilot/issues).

## License

Proprietary and confidential. Copyright © 2026 Silvexis. All rights reserved.
Unauthorized use, copying, or distribution is strictly prohibited.
