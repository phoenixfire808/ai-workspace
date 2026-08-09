FROM node:22-bookworm-slim AS dependencies

WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM dependencies AS builder

ARG NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

COPY frontend/ ./
RUN npm run typecheck && npm run build

FROM node:22-bookworm-slim AS runner

WORKDIR /workspace/frontend
ENV NODE_ENV=production

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --omit=dev
COPY --from=builder /workspace/frontend/.next ./.next

EXPOSE 3000

CMD ["npm", "run", "start", "--", "--hostname", "0.0.0.0", "--port", "3000"]
