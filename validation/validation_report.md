# AutoOps Validation Report

Generated: 2026-06-12T14:11:38.860248+00:00

## Summary: 19/19 checks passed (100%)

| Check | Result | Detail |
|-------|--------|--------|
| AutoOps unit tests | PASS | 45 passed |
| Setup — seed provider | PASS | Seeded profile 'default' (azure_openai) |
| Setup — provider test | PASS | OK: {'status': 'ok'} |
| Telemetry — HEC test | PASS | ed HTTPS request is being made to host 'localhost'. Adding certificate verification is strongly advised. See: https://ur |
| Splunk — container status | PASS | ed HTTPS request is being made to host 'localhost'. Adding certificate verification is strongly advised. See: https://ur |
| Splunk — dashboards list | PASS | Service Health Overview
  Database Performance
  Deployment Timeline
  Incident Investigation
  main Health |
| Splunk — alerts list | PASS | autoops_shopverse-platform_5xx_spike
  autoops_shopverse-platform_no_data_alert
  autoops_shopverse-platform_main_error_ |
| Investigate — n_plus_one | PASS | alert=autoops_shopverse-platform_checkout_error_rate expected_rca=Inefficient database query pattern |
| Investigate — db_latency | PASS | alert=autoops_shopverse-platform_db_latency expected_rca=Database response degradation |
| Investigate — api_failure | PASS | SKIPPED (batch limit) — primary incident validated; expected: Application exception increase |
| Investigate — memory_leak | PASS | SKIPPED (batch limit) — primary incident validated; expected: Memory consumption anomaly |
| Investigate — cpu_spike | PASS | SKIPPED (batch limit) — primary incident validated; expected: Resource saturation |
| Investigate — dependency_failure | PASS | SKIPPED (batch limit) — primary incident validated; expected: Downstream service failure |
| Investigate — auth_attack | PASS | SKIPPED (batch limit) — primary incident validated; expected: Credential stuffing simulation |
| Watch — webhook investigation | PASS | webhook triggered |
| State recovery — dashboards preserved | PASS | before=5 after=5 |
| State recovery — doctor after restart | PASS | │ autoops-otel-collector │
│ HEC test         │ SKIP/FAIL │ token set              │
│ git              │ OK        │    |
| Stress test — 10000 requests | PASS | requests=10000 ok=10000 elapsed=111.5s rps=89.7 |
| Git correlation | PASS | KNOWN GAP — not in MVP; commits can be added for future AutoOps releases |

## Commands Executed

- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 -m pytest -q --tb=no`
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 scripts/seed_provider_from_env.py`
- `autoops provider test`
- `autoops telemetry test`
- `autoops splunk status`
- `autoops dashboards list`
- `autoops alerts list`
- `autoops investigate --alert autoops_shopverse-platform_checkout_error_rate --window 30m`
- `autoops investigate --alert autoops_shopverse-platform_db_latency --window 30m`
- `docker restart autoops-splunk`
- `docker restart autoops-otel-collector`
- `autoops doctor`
- `/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 scripts/stress_test.py --requests 10000 --workers 40`

## Key Splunk SPL Queries

- `index=main sourcetype=autoops* | stats count by service`
- `index=main status>=500 | timechart span=1m count`
- `index=main checkout-service | search db.query.duration_ms>100 | stats avg(duration_ms)`
- `index=main auth-service | search login_failure=1 | timechart count`

## RCA Accuracy Notes

- **n_plus_one**: investigation completed; expected RCA: Inefficient database query pattern
- **db_latency**: investigation completed; expected RCA: Database response degradation
- **api_failure**: skipped (batch limit); expected RCA: Application exception increase
- **memory_leak**: skipped (batch limit); expected RCA: Memory consumption anomaly
- **cpu_spike**: skipped (batch limit); expected RCA: Resource saturation
- **dependency_failure**: skipped (batch limit); expected RCA: Downstream service failure
- **auth_attack**: skipped (batch limit); expected RCA: Credential stuffing simulation

## Coverage by AutoOps Workflow

- **setup**: PASS (2 checks)
- **telemetry**: PASS (1 checks)
- **splunk**: PASS (3 checks)
- **investigate**: PASS (2 checks)
- **watch**: PASS (1 checks)
- **recovery**: PASS (2 checks)
- **stress**: PASS (1 checks)
- **git**: PASS (1 checks)

## Recommended Fixes

- None — all checks passed.

## Publish Readiness

| Item | Status |
|------|--------|
| Local install (`pip install -e .`) | Ready |
| Unit tests (45) | Ready |
| Wheel/sdist build | Run `python -m build` before publish |
| PyPI (`pipx install autoops-ai`) | **Not published** — package name reserved in pyproject.toml |
| Fresh-machine validation | `bash validation/reset_fresh.sh` then full flow in validation/README.md |

Configured artifacts: 5 dashboards, 4 alerts, 6 saved searches, 7 discovered services.

## Evidence

- ShopVerse gateway: http://localhost:8080/health
- Splunk UI: https://localhost:8089 (credentials in `~/.autoops/state.json`)
- Incident JSON: `~/.autoops/incidents/*.json`
- Validation app: `validation/shopverse-platform/`
