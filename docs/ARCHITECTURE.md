# AutoOps AI Architecture

![AutoOps Architecture](../architecture.png)

## How it integrates with your project

### 1. Install & setup (one time)

```bash
pipx install autoops-ai
autoops setup          # LLM provider → OS keychain
```

### 2. Configure any repo

```bash
cd /path/to/your-app
autoops configure --repo .
```

AutoOps runs six phases automatically:

| Phase | What happens | Touches your project |
|-------|----------------|----------------------|
| **Discovery** | Scans files + LLM maps services, DBs, critical paths | Writes `~/.autoops/architecture.json` |
| **Instrumentation** | Generates logging/tracing middleware | Adds `autoops_middleware.py`, `autoops_db_tracing.py` |
| **Splunk Config** | Creates dashboards, alerts, saved searches | Splunk only (named `autoops_{app}_*`) |
| **Evidence** | Queries Splunk when investigating | Read-only |
| **RCA** | LLM analyzes evidence → root causes | Writes `~/.autoops/incidents/*.json` |
| **Remediation** | LLM suggests fixes | Recommendations in incident report |

### 3. Infrastructure AutoOps bootstraps (Docker)

| Container | Ports | Role |
|-----------|-------|------|
| `autoops-splunk` | 8000 UI, 8088 HEC, 8089 REST | Log storage, dashboards, alerts |
| `autoops-otel-collector` | 4317 gRPC, 4318 HTTP | Traces/metrics → Splunk HEC |

### 4. Telemetry from your app → Splunk

**Path A — Direct HEC (generated middleware)**

```
Your FastAPI service → JSON logs → Splunk HEC :8088 → index=main
```

**Path B — OpenTelemetry**

```
Your app → OTel SDK → Collector :4317/:4318 → Splunk HEC → index=main
```

Set in your app's environment (e.g. Docker Compose):

```yaml
SPLUNK_HEC_URL: https://host.docker.internal:8088/services/collector/event
SPLUNK_HEC_TOKEN: ${SPLUNK_HEC_TOKEN}   # from ~/.autoops/state.json after configure
```

### 5. Incident workflow

```bash
# Splunk alert fires (or manual)
autoops investigate --alert autoops_your-app_db_latency --window 30m

# Or webhook listener
autoops watch --port 9000
```

### 6. Local state (`~/.autoops/`)

| File | Contents |
|------|----------|
| `state.json` | Splunk credentials, HEC token, dashboard/alert names |
| `architecture.json` | Discovered services, endpoints, critical paths |
| `incidents/` | Investigation reports (evidence + RCA + remediation) |
| `config.json` | LLM profile metadata (keys in OS keychain) |

## Data flow legend

| Color | Meaning |
|-------|---------|
| Dashed blue | Control / orchestration (CLI → agents) |
| Orange | External API (LLM, Splunk REST, Splunk MCP) |
| Solid blue | Log ingestion via HEC |
| Teal | Telemetry via OpenTelemetry |

## Supported LLM providers

OpenAI · Claude (Anthropic) · Azure OpenAI · OpenRouter · Amazon Bedrock

Credentials stored in macOS Keychain / Windows Credential Locker via `autoops setup`.
