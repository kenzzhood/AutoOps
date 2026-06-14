# Built With

Technologies used in AutoOps AI.

## Core product

| Category | Technologies |
|----------|--------------|
| Language | Python 3.11+ |
| CLI | Typer, Rich, Questionary |
| Data models | Pydantic |
| Templates | Jinja2 |
| HTTP | httpx, requests |
| Secrets | keyring (macOS Keychain / Windows Credential Locker) |
| Testing | pytest, pytest-asyncio, pytest-mock |
| Packaging | setuptools, PyPI (`autoops-ai`) |

## AI / LLM

- OpenAI API
- Anthropic Claude API
- Azure OpenAI
- OpenRouter
- Amazon Bedrock (boto3)

## Observability

- Splunk Enterprise (Docker: `splunk/splunk`)
- Splunk REST API and HEC (HTTP Event Collector)
- Splunk MCP (Model Context Protocol)
- OpenTelemetry Collector (`otel/opentelemetry-collector-contrib`)
- OTLP (gRPC `:4317`, HTTP `:4318`)

## Validation and demo apps

- FastAPI, Uvicorn
- SQLAlchemy, PostgreSQL, Redis
- Docker Compose
- JWT (PyJWT)

## Infrastructure

- Docker Desktop
- GitHub (source)
- PyPI (distribution)
