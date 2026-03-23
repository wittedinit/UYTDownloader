FROM node:22-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .

ENV NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM node:22-alpine

WORKDIR /app

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

ENV HOSTNAME=0.0.0.0
ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
