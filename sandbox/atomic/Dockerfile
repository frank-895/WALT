# syntax=docker/dockerfile:1

ARG ATOMIC_CRM_REF=167a4cdb652b1ab2b4b030831cfa7adcf2099321

FROM node:22.22.1-bookworm-slim AS build

ARG ATOMIC_CRM_REF

WORKDIR /src

ADD https://github.com/marmelab/atomic-crm.git#${ATOMIC_CRM_REF} .
RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts
RUN npm run build:demo
RUN find dist -type f -name '*.map' -delete

FROM cgr.dev/chainguard/nginx@sha256:f801aa4ac908f6c3847efe81b577e4f34e1f237b5556dfbe698127ad464db269 AS production

ARG ATOMIC_CRM_REF

LABEL org.opencontainers.image.title="WALT Atomic CRM demo" \
      org.opencontainers.image.description="A deterministic Atomic CRM demo environment for WALT sandboxes" \
      org.opencontainers.image.source="https://github.com/frank-895/WALT" \
      org.opencontainers.image.licenses="MIT" \
      io.walt.atomic-crm.revision="${ATOMIC_CRM_REF}"

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist/ /usr/share/nginx/html/
COPY --from=build /src/LICENSE.md /usr/share/licenses/atomic-crm/LICENSE.md

EXPOSE 8080

HEALTHCHECK --interval=5s --timeout=3s --start-period=5s --retries=10 \
    CMD ["/usr/sbin/nginx", "-t"]

CMD ["-c", "/etc/nginx/nginx.conf", "-e", "/dev/stderr", "-g", "daemon off;"]
