# AutoOps AI — Architecture Diagram

This document accompanies the required architecture diagram at the repository root.

## Diagram

![AutoOps AI Architecture](architecture_diagram.png)

## End-to-end flow

![AutoOps Complete Flow](autoops-complete-flow.png)

## Component overview

| Layer | Components |
|-------|------------|
| **CLI** | `autoops setup`, `configure`, `investigate`, `watch`, `doctor` |
| **Orchestration** | Discovery → Instrumentation → Splunk Config → Evidence → RCA → Remediation |
| **LLM** | OpenAI, Claude, Azure OpenAI, OpenRouter, Amazon Bedrock (via OS keychain) |
| **Observability** | Splunk Enterprise (Docker), OpenTelemetry Collector, HEC ingestion |
| **Target app** | Any repo — AutoOps generates middleware and DB tracing |
| **State** | `~/.autoops/state.json`, `architecture.json`, `incidents/` |

## Data flows

1. **Logs** — App → Splunk HEC (`:8088`) → dashboards and alerts
2. **Telemetry** — App → OTel Collector (`:4317`/`:4318`) → Splunk HEC
3. **Investigation** — Splunk alert or webhook → Evidence Agent → RCA Agent → Remediation Agent

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for integration details.
