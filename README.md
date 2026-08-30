# WALT

Walkthrough agent, live and talkative.

## Development

```sh
docker compose -f docker-compose.yml up --build
```

The project includes a Lefthook pre-commit hook that formats staged files and runs the relevant project checks automatically.

## Production

The frontend runs on Vercel at [walt.ink](https://walt.ink) in the `walt-frontend` project.

The FastAPI backend runs on Vercel at [api.walt.ink](https://api.walt.ink/api/health) in the `walt-api` project.

Daytona hosts the persistent desktop environment. OpenAI Realtime connects directly to the browser over WebRTC, while the backend handles short-lived session setup and server-side credentials.
