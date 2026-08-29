# Atomic CRM demo image

This image packages the official Atomic CRM in-memory demo for disposable Daytona sandboxes.

Build and test it locally:

```sh
docker build --platform linux/amd64 --tag frank895/walt-atomic-demo:local sandbox/atomic
docker run --rm --publish 8080:8080 frank895/walt-atomic-demo:local
```

Publish a version after signing in with `docker login`:

```sh
docker buildx build --platform linux/amd64 --tag frank895/walt-atomic-demo:0.1.0 --tag frank895/walt-atomic-demo:latest --provenance=mode=max --sbom=true --push sandbox/atomic
```
