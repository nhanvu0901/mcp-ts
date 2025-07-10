
FROM node:18-alpine AS builder

WORKDIR /app


COPY package*.json ./
COPY tsconfig.mcp.json ./


RUN npm ci && npm cache clean --force


COPY src/ ./src/


RUN npm run build


FROM node:18-alpine AS production

WORKDIR /app


RUN apk add --no-cache curl


COPY package*.json ./


RUN npm ci --only=production && npm cache clean --force


COPY --from=builder /app/dist ./dist


RUN mkdir -p data/uploads logs


RUN addgroup -g 1001 -S nodejs && \
    adduser -S fastify -u 1001


RUN chown -R fastify:nodejs /app


USER fastify


EXPOSE 3000


HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:3000/health || exit 1


CMD ["node", "dist/main.js"]