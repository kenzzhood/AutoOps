# AutoOps Validation Suite

Official end-to-end validation for AutoOps using **ShopVerse Platform**.

## Quick Start

```bash
# 1. Fresh-machine reset (optional)
bash validation/reset_fresh.sh

# 2. Install AutoOps
pip install -e .

# 3. Seed LLM profile from .env
python3 scripts/seed_provider_from_env.py

# 4. Start ShopVerse
cd validation/shopverse-platform && docker compose up -d --build

# 5. Configure observability
autoops configure --repo validation/shopverse-platform

# 6. Run full validation
python3 validation/run_validation.py
```

## ShopVerse Platform

Location: [validation/shopverse-platform](shopverse-platform)

- 7 microservices + React frontend + Postgres + Redis
- 7 injectable incident types via `POST /admin/incidents/enable?type=...`
- Stress test: `python3 validation/shopverse-platform/scripts/stress_test.py --requests 10000`

## Report

After running validation, see [validation_report.md](validation_report.md).
