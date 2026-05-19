# ============================================================
# FieldPro Frontend — Multi-stage Dockerfile
# ============================================================

# --- Stage 1: Dependencies ---
FROM node:20-alpine AS deps

RUN apk add --no-cache libc6-compat
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --frozen-lockfile

# --- Stage 2: Development ---
FROM node:20-alpine AS development

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
# Copy root config files (src/ and public/ are mounted as volumes in dev)
COPY package.json package-lock.json* tsconfig.json tailwind.config.ts next.config.mjs middleware.ts postcss.config.js ./
EXPOSE 3000
ENV NEXT_TELEMETRY_DISABLED=1
CMD ["npm", "run", "dev"]

# --- Stage 3: Builder ---
FROM node:20-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# --- Stage 4: Production ---
FROM node:20-alpine AS production

LABEL maintainer="FieldPro Engineering <engineering@yourfieldpro.com>"

RUN apk add --no-cache curl

WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create non-root user
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy Next.js standalone build output
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:3000/api/health || exit 1

CMD ["node", "server.js"]
