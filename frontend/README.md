# Frontend (Next.js)

## Dev

Install deps (uses local npm via Node):

```bash
cd frontend
node ../.tooling/package/bin/npm-cli.js install
node ../.tooling/package/bin/npm-cli.js run dev
```

Then open `http://localhost:3000`.

## Backend integration

The UI calls `POST /api/stream` (Next.js route), which proxies to your backend
research stream at:

`process.env.NEXT_PUBLIC_BACKEND_URL` + `process.env.NEXT_PUBLIC_BACKEND_STREAM_PATH`

(for example `http://localhost:8000` + `/research`). If either variable is
missing, the route returns HTTP 503 with a JSON error (no mock stream).

When proxying FastAPI `/research` SSE responses, the route normalizes them into
NDJSON token/trace messages for the frontend stream parser.

### Expected streaming format

NDJSON over a chunked HTTP response. Each line is either:

- `{"type":"token","text":"..."}` (append to the answer)
- `{"type":"trace","event":{ "id":"...", "ts": 1710000000000, "type":"...", "payload":{...}}}` (append to trace list)
