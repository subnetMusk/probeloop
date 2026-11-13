# syntax=docker/dockerfile:1
# Build context: the repository root (see .dockerignore).
# Development only: Vite with hot module replacement, behind `docker compose watch`.
# At runtime the backend serves the built app (see backend.Dockerfile).

FROM node:24.22.0-trixie-slim AS dev
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node frontend/package.json frontend/package-lock.json ./
RUN --mount=type=cache,target=/home/node/.npm,uid=1000,gid=1000 npm ci --no-audit --no-fund
COPY --chown=node:node frontend/ ./
# The production build reads the notices that packages do not ship, as the runtime image does.
COPY --chown=node:node licenses/ /licenses/
# The frontend and backend test the same immutable report presentation contract.
COPY --chown=node:node backend/tests/fixtures/synthetic/assessment/report-outline.json /backend/tests/fixtures/synthetic/assessment/report-outline.json
EXPOSE 5173
CMD ["npm", "run", "dev"]
