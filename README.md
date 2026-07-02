# Everpilot

**Autonomous code-maintenance for GitHub repositories.** An autopilot, not a copilot, for your codebase.

Everpilot takes the wheel. Delegate the ongoing care of a codebase to it and choose, per capability, whether it works fully autonomously or hands the final commit to a human for review.

## Capabilities

| Capability | Description |
|---|---|
| 🛡️ Security | Continuously reviews for vulnerabilities and lands fixes |
| 🎫 Issue Triage | Reads new issues, classifies them, proposes and ships fixes |
| 📦 Dependencies | Keeps third-party libraries current; absorbs Dependabot-style updates |
| 🧪 Test Hygiene | Runs the test suite, diagnoses failures, opens fixes |
| ✨ Freshness | General modernization so the codebase never rots |

Each capability is independently toggleable with three modes: **Autopilot** (fully autonomous), **Assisted** (opens a PR and waits for human approval), or **Off**.

## Project structure

```
everpilot/
├── backend/        # Python / FastAPI (uv)
├── frontend/       # TypeScript / React / Vite
├── amplify.yml     # AWS Amplify build config
└── .github/
    └── workflows/
        └── ci.yml  # GitHub Actions CI
```

## Local development

### Backend

```bash
cd backend
cp .env.example .env   # fill in GitHub App credentials
uv sync --all-groups
uv run uvicorn everpilot.main:app --reload
```

API available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs` (when `DEBUG=true`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

App available at `http://localhost:5173`. API calls are proxied to the backend.

### Tests (backend)

```bash
cd backend
uv run pytest
```

### Lint & format

```bash
cd backend
uv run ruff check .
uv run ruff format .
```

## Deployment

The frontend is deployed to [AWS Amplify](https://aws.amazon.com/amplify/) at:
- [everpilot.ai](https://everpilot.ai)
- [everpilot.dev](https://everpilot.dev)
- [everpilot.io](https://everpilot.io)

The `amplify.yml` at the root configures the build.

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a pull request targeting `develop`
