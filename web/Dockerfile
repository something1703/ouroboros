# Phase 10 (submission prep): a public static-hosting service for the built SPA, so
# judges have a real URL instead of having to run `npm run dev` locally. Build args
# supply the two VITE_* values baked into the JS bundle at build time (Vite inlines
# `import.meta.env.*` at build, not at container runtime -- there is no env var to
# set on the running container that would change them after the image is built).
#
# Build context is the repo root (not web/) -- this image needs the root
# ouroboros_architecture.mermaid file alongside web/, matching web/cloudbuild.yaml.
#   docker build -f web/Dockerfile -t web-image \
#     --build-arg VITE_API_BASE_URL=https://dashboard-api-492372502792.us-central1.run.app \
#     --build-arg VITE_GOOGLE_CLIENT_ID=492372502792-58fivlikum2o43klt2gbb9j16fqqr1qb.apps.googleusercontent.com \
#     .
#   gcloud run deploy web --image ... --allow-unauthenticated --region us-central1

FROM node:20-slim AS build
WORKDIR /repo
# The image mirrors the real repo layout (ouroboros_architecture.mermaid at the
# root, web/ as a sibling) rather than flattening web/ into the build root --
# DocsArticlePage's `../../../../ouroboros_architecture.mermaid?raw` import (the
# site's single source of truth for the architecture diagram, shared with
# README.md's own embed) resolves relative to that real layout, and a flattened
# image silently breaks it with no local repro (found live: this build failed
# with "Module not found" the first time, while `npm run build` from a checkout
# had always succeeded).
COPY ouroboros_architecture.mermaid ./ouroboros_architecture.mermaid
COPY web/package.json web/package-lock.json ./web/
WORKDIR /repo/web
RUN npm ci
COPY web/ ./
ARG VITE_API_BASE_URL
ARG VITE_GOOGLE_CLIENT_ID
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
ENV VITE_GOOGLE_CLIENT_ID=${VITE_GOOGLE_CLIENT_ID}
RUN npm run build

FROM nginx:1.27-alpine
COPY web/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /repo/web/dist /usr/share/nginx/html
# Cloud Run injects PORT=8080 by default for a fresh service; hardcoded to match
# rather than templated, since this image has no other reason to vary its port.
EXPOSE 8080
