# syntax=docker/dockerfile:1

FROM node:24.20.0-slim AS base

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable && corepack prepare pnpm@11.24.0 --activate

WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --ignore-scripts

FROM base AS development

ENV CI=true \
    PNPM_CONFIG_IGNORE_SCRIPTS=true

COPY . .
EXPOSE 5173
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173"]

FROM base AS build

COPY . .
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.29-alpine AS production

COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
