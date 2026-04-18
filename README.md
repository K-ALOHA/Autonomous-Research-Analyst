# 🔥 Autonomous Research Analyst

Autonomous Research Analyst is a production-style, multi-agent research system that converts a user question into a structured, source-backed report with transparent reasoning traces and export-ready output.

## 🧠 Problem It Solves

Research workflows are often slow, inconsistent, and difficult to audit. Analysts jump between search tabs, notes, and writing tools, with little traceability.

This project solves that by orchestrating specialized agents that:

- break down a query into executable subtasks,
- gather evidence from the web,
- synthesize insights with citations,
- critique output quality,
- and produce a polished final report (including PDF export).

## ⚙️ Architecture (Multi-Agent System)

The backend runs a LangGraph workflow with explicit state transitions:

`Planner -> Search (parallel fan-out) -> Analyst -> Critic -> Editor`

- `Planner`: turns a user query into a structured plan and search queries.
- `Search`: executes parallel Tavily searches for breadth and speed.
- `Analyst`: synthesizes findings using OpenRouter-hosted LLMs.
- `Critic`: scores confidence and flags quality risks.
- `Editor`: creates the final markdown report and source list.

API and delivery layers:

- FastAPI backend exposes `/research` (SSE + JSON mode) and PDF export.
- Next.js frontend streams traces in real time and supports report download.

## 🚀 Features

- Multi-agent research pipeline with explicit orchestration.
- Parallel web search integration with Tavily.
- OpenRouter integration for Planner + Analyst LLM calls.
- Real-time trace stream for step-by-step execution visibility.
- Citation-aware final report generation.
- One-click PDF export: `GET /research/{run_id}/export/pdf`.
- Modern frontend with agent status indicators and trace panel.

## 🧱 Tech Stack

- Backend: FastAPI, LangGraph, Pydantic, HTTPX
- LLM Gateway: OpenRouter (OpenAI-compatible client)
- Search: Tavily API
- Frontend: Next.js (App Router), React, TypeScript, Tailwind CSS
- Export: `fpdf2` for PDF rendering
- Deployment: Docker Compose + Cloud Run templates

## 📸 Screenshots

> Add product screenshots/GIFs before publishing.

- `docs/screenshots/dashboard.png` - Main query + streaming output view
- `docs/screenshots/trace-panel.png` - Agent trace timeline and stage states
- `docs/screenshots/report-citations.png` - Final report with clickable citations
- `docs/screenshots/pdf-export.png` - PDF download/export UX

## 🛠️ Setup

### 1) Clone and configure environment

```bash
git clone <your-repo-url>
cd "Autonomous Research Analyst"
cp .env.example .env
```

Fill required keys in `.env`:

- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY`

### 2) Run with Docker (recommended)

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

Stop:

```bash
docker compose down
```

### 3) Local development (without Docker)

Backend:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Render / platforms expecting `main:app`:** from the repo root, use the shim module `main.py`:

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 10000
```

Frontend:

```bash
cd frontend
node ../.tooling/package/bin/npm-cli.js install
node ../.tooling/package/bin/npm-cli.js run dev
```

## 🔌 API Quick Start

Run research (non-streaming JSON):

```bash
curl -X POST "http://localhost:8000/research" \
  -H "Content-Type: application/json" \
  -d '{"query":"Latest EV battery recycling outlook","stream":false,"include_traces":true}'
```

Export PDF:

```bash
curl -L "http://localhost:8000/research/<run_id>/export/pdf" -o research-report.pdf
```

Health check:

```bash
curl "http://localhost:8000/health"
```

## 📁 Project Structure

```text
backend/      # API, agents, workflow, runtime, services
frontend/     # Next.js UI + API proxy routes
scripts/      # e2e + utility scripts
deploy/       # Cloud Run service templates
```

## 📌 Production Notes

- Run behind a reverse proxy/load balancer in production.
- Configure secret management for API keys (not plaintext env files).
- Add persistent run storage (DB/Redis) if multi-instance export retention is required.
