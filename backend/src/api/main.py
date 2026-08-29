from fastapi import FastAPI

app = FastAPI(title="WALT API")


@app.get("/api/health")
def health() -> dict[str, str]:
    """Report whether the API is ready to receive requests."""
    return {"status": "ok"}
