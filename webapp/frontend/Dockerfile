# Next.js dashboard (standalone). Build context is the REPO ROOT.
#   docker build -f webapp/frontend/Dockerfile --build-arg NEXT_PUBLIC_API_BASE=https://acct.example.com/api .

FROM node:20-alpine AS deps
WORKDIR /app
COPY webapp/frontend/package.json webapp/frontend/package-lock.json ./
RUN npm ci

FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY webapp/frontend/ ./
# Default empty = same-origin: the browser calls /api/* and the Next server
# proxies to the backend at runtime (BACKEND_INTERNAL_URL). This keeps the image
# portable. Set an absolute URL here only if you want to call the API directly.
ARG NEXT_PUBLIC_API_BASE=""
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
