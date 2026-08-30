# syntax=docker/dockerfile:1

ARG ATOMIC_CRM_REF=167a4cdb652b1ab2b4b030831cfa7adcf2099321
ARG BROWSER_USE_VERSION=0.13.8
ARG CHROMIUM_VERSION=151.0.7922.173-1~deb12u1

FROM node:22.22.1-bookworm-slim AS build

ARG ATOMIC_CRM_REF

WORKDIR /src

ADD https://github.com/marmelab/atomic-crm.git#${ATOMIC_CRM_REF} .
COPY demo/App.tsx demo/App.tsx
COPY seed.json public/seed.json
RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts
RUN npm run build:demo
RUN find dist -type f -name '*.map' -delete

FROM python:3.12-slim-bookworm AS production

ARG ATOMIC_CRM_REF
ARG BROWSER_USE_VERSION
ARG CHROMIUM_VERSION

USER root

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /uvx /usr/local/bin/

ENV UV_TOOL_DIR=/opt/uv-tools \
    UV_TOOL_BIN_DIR=/usr/local/bin

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
        "chromium=${CHROMIUM_VERSION}" \
        "chromium-common=${CHROMIUM_VERSION}" \
        curl \
        dbus-x11 \
        nginx \
        novnc \
        procps \
        xfce4 \
        xfce4-terminal \
        x11-utils \
        x11vnc \
        xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 daytona \
    && useradd --uid 1000 --gid daytona --create-home --shell /bin/bash daytona \
    && uv tool install --python /usr/local/bin/python3 "browser-use==${BROWSER_USE_VERSION}" \
    && browser-use --help >/dev/null

ENV VNC_RESOLUTION=1920x1080 \
    ATOMIC_URL=http://127.0.0.1:8080 \
    CHROMIUM_CDP_URL=http://127.0.0.1:9222 \
    DISPLAY=:0

LABEL org.opencontainers.image.title="WALT Atomic CRM demo" \
      org.opencontainers.image.description="Atomic CRM, Chromium, and Browser Use prepared for WALT Daytona sandboxes" \
      org.opencontainers.image.source="https://github.com/frank-895/WALT" \
      org.opencontainers.image.licenses="MIT" \
      io.walt.atomic-crm.revision="${ATOMIC_CRM_REF}" \
      io.walt.browser-use.version="${BROWSER_USE_VERSION}" \
      io.walt.chromium.version="${CHROMIUM_VERSION}"

WORKDIR /opt/atomic

COPY nginx.conf /opt/atomic/nginx.conf
COPY start-demo /usr/local/bin/start-demo
COPY --from=build /src/dist/ /opt/atomic/dist/
COPY --from=build /src/LICENSE.md /usr/share/licenses/atomic-crm/LICENSE.md

RUN chmod 0755 /usr/local/bin/start-demo \
    && chmod -R a+rX /opt/atomic \
    && chown -R daytona:daytona /opt/atomic \
    && chmod u+w /opt/atomic/dist/seed.json /opt/atomic/dist

USER daytona

EXPOSE 8080

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
    CMD ["curl", "--fail", "--silent", "http://127.0.0.1:8080/healthz"]

CMD ["nginx", "-c", "/opt/atomic/nginx.conf", "-g", "daemon off;"]
