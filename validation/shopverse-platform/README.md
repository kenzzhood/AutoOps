# ShopVerse Platform

Official AutoOps validation environment — production-style e-commerce microservices.

## Architecture

- **Frontend** — React-style customer portal (static SPA on port 3000)
- **API Gateway** — port 8080
- **Auth Service** — JWT login/registration
- **Product Service** — catalog and search
- **Checkout Service** — cart, checkout, PostgreSQL + Redis
- **Order Service** — order persistence
- **Notification Service** — email via mock provider
- **Email Mock** — external dependency simulation

## Start

```bash
docker compose up -d --build
curl http://localhost:8080/health
```

## Incident Injection

```bash
curl -X POST "http://localhost:8080/admin/incidents/enable?type=n_plus_one"
curl -X POST "http://localhost:8080/admin/incidents/disable"
```

Types: `n_plus_one`, `db_latency`, `api_failure`, `memory_leak`, `cpu_spike`, `dependency_failure`, `auth_attack`

## AutoOps Validation

```bash
autoops configure --repo validation/shopverse-platform
python3 validation/run_validation.py
```

## Stress Test

```bash
python3 scripts/stress_test.py --requests 10000 --workers 50
```
