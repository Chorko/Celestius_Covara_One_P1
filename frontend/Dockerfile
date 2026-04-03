# ── Frontend (Next.js 16 + Node 22) ──────────────────────────────────
# Multi-stage build: build → production with standalone output.

FROM node:22-alpine AS base
WORKDIR /app

# ── Stage 1: Install dependencies ────────────────────────────────────
FROM base AS deps

# libc6-compat needed for some native Node modules
RUN apk add --no-cache libc6-compat

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --frozen-lockfile --ignore-scripts

# ── Stage 2: Build the Next.js app ───────────────────────────────────
FROM base AS builder

COPY --from=deps /app/node_modules ./node_modules
COPY frontend/ .

# Build-time env vars (non-secret, public keys only)
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_API_URL=/api

ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Enable standalone output for Docker
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Stage 3: Production image ────────────────────────────────────────
FROM base AS production

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy built artifacts
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
