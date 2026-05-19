FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_API_URL é build-time (inlined no bundle do client). Em produção
# Railway, definir nas variáveis do serviço — Railway repassa como build arg
# quando a key começa com NEXT_PUBLIC_. Em dev local, docker-compose.yml já
# injeta via build.args (ver linhas 50-52 do compose).
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
# Next.js standalone (server.js) lê PORT do environment a cada start.
# - Em Railway: PORT é dinamicamente injetada (ex.: 8080) e o roteamento
#   HTTPS aponta pra ela. Sem `ENV PORT=...` no Dockerfile, Next.js usa
#   o valor injetado em runtime.
# - Em dev local (docker-compose), sem PORT setado, Next.js usa default
#   3000, que docker-compose mapeia para `${FRONTEND_HOST_PORT:-13000}:3000`.
# EXPOSE 3000 é apenas documentação — Railway descobre a porta real
# via PORT env, não via EXPOSE.
EXPOSE 3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
