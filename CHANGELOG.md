# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Added
- Initial project setup and structure
- Python/FastAPI backend with uv package management
- React/TypeScript/Vite frontend
- Five core capabilities: Security, Issue Triage, Dependencies, Test Hygiene, Freshness
- Per-capability operating modes: Autopilot, Assisted, Off
- Repository install/uninstall API endpoints
- GitHub webhook receiver with HMAC signature verification
- AWS Amplify build configuration (`amplify.yml`)
- GitHub Actions CI workflow (backend tests + frontend build)
- Landing page with hero, capabilities grid, and mode explanations
- Dashboard page listing installed repositories
- Repo detail page with live capability toggles
- Comprehensive README with setup instructions, env var reference,
  GitHub App creation guide, API reference, and deployment docs

### Changed
- Upgrade backend to Python 3.13

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A

## Notes
- This software is proprietary and confidential. All rights reserved by Silvexis.
