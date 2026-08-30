# Atomic CRM demo image

This image packages Atomic CRM's production demo frontend with Chromium, Browser Use, and Daytona's required desktop packages for disposable Daytona sandboxes. Atomic uses an in-memory FakeRest data provider with its original artificial latency. Every browser start removes the previous Chromium profile and loads the CRM from `/opt/atomic/dist/seed.json`.

## Build locally

```sh
docker build --platform linux/amd64 --tag frank895/walt-atomic-demo:local demo_images/atomic
```

The image starts the Atomic static server on port 8080. Chromium starts separately because Daytona Computer Use must create the graphical display first.

```sh
docker run --rm --publish 8080:8080 frank895/walt-atomic-demo:local
```

## Publish to Docker Hub

Use an immutable version for every published build. Daytona snapshots do not accept moving tags such as `latest`.

```sh
docker login
docker buildx build --platform linux/amd64 --tag frank895/walt-atomic-demo:1.0.1 --provenance=mode=max --sbom=true --push demo_images/atomic
```

## Create the Daytona snapshot

Create the snapshot once from the versioned Docker Hub image. Customer sandboxes must use the snapshot rather than the Docker Hub image directly.

```sh
daytona snapshot create atomic-realtime-demo-v1 --image docker.io/frank895/walt-atomic-demo:1.0.1 --cpu 2 --memory 4
```

The snapshot should use the default `daytona` user and the resolution baked into the image. Do not add per-customer environment variables, volumes, secrets, or data to the snapshot.

## Start a demo sandbox

Create a sandbox from `atomic-realtime-demo-v1`, start Daytona Computer Use, upload the visitor's seed to `/opt/atomic/dist/seed.json`, and execute `start-demo`. The command starts one visible Chromium instance with a fresh profile and exposes its CDP endpoint only inside the sandbox at `http://127.0.0.1:9222`.

Browser Use connects to that existing browser through the `BU_CDP_URL` environment variable. The smoke test must inspect the real page and its accessibility tree:

```sh
BU_CDP_URL=http://127.0.0.1:9222 browser-use <<'PY'
ensure_real_tab()
print(page_info())
nodes = cdp("Accessibility.getFullAXTree")["nodes"]
links = {
    node.get("name", {}).get("value")
    for node in nodes
    if node.get("role", {}).get("value") == "link"
}
required_links = {"Companies", "Contacts", "Deals"}
print(f"CRM links: {sorted(required_links & links)}")
assert required_links <= links
PY
```

The sandbox is ready when `http://127.0.0.1:8080/healthz` and `http://127.0.0.1:9222/json/version` both respond and Browser Use can inspect the Atomic page.
