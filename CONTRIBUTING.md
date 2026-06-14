# Contributing to AutoOps AI

Thank you for your interest in contributing to AutoOps AI. This guide covers setup, development workflow, and pull request expectations.

## Getting Started

### Fork and clone

```bash
git clone https://github.com/YOUR_USERNAME/AutoOps.git
cd AutoOps
git remote add upstream https://github.com/kenzzhood/AutoOps.git
```

### Install for development

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

All 45 unit tests should pass before opening a PR.

### Optional: end-to-end validation

See [validation/README.md](validation/README.md) for the ShopVerse validation suite.

---

## Development Workflow

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. Make your changes in the `autoops/` package or tests.

3. Run tests and lint locally:
   ```bash
   pytest -q
   ```

4. Commit with a clear message:
   ```bash
   git commit -m "feat: add support for ..."
   ```

5. Push and open a Pull Request against `kenzzhood/AutoOps` `main`.

---

## Code Style

- Python 3.11+ with type hints where practical
- Follow existing patterns in `autoops/` (Typer CLI, Pydantic models, async agents)
- Keep functions focused; prefer small modules under `autoops/agents/`, `autoops/splunk/`, etc.
- Add or update tests in `tests/` for new behavior

---

## Security — Required for All PRs

**Never commit secrets.** This includes:

- API keys (OpenAI, Azure, Anthropic, AWS, etc.)
- Splunk passwords or HEC tokens
- PyPI tokens
- Real endpoints tied to your personal cloud resources

**Do:**

- Use environment variables and `.env` (gitignored)
- Use `autoops setup` / OS keychain for credential storage
- Reference `.env.example` for placeholder values only
- Keep demo/validation passwords clearly local-only (e.g. `shopverse`, `changeme`)

**Do not:**

- Add hardcoded tokens or keys in source code
- Commit `.env`, `~/.autoops/`, or `validation/run_output.log`
- Include real credentials in test fixtures

If you accidentally commit a secret, rotate the credential immediately and force-push a fix.

---

## Project Structure

```
autoops/           # Main package (CLI, agents, Splunk, LLM, telemetry)
tests/             # pytest suite
validation/        # ShopVerse end-to-end validation app
demo-app/          # Simple FastAPI demo
scripts/           # install.sh, seed_provider_from_env.py
docs/              # Architecture documentation
```

---

## Reporting Issues

Open an issue on GitHub with:

- AutoOps version (`autoops --help` or `pip show autoops-ai`)
- OS and Python version
- Steps to reproduce
- Relevant logs (redact secrets)

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
