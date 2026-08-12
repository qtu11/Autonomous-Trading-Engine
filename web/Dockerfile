# ATE Frontend — production build (next build → next start)
# BUG FIX: trước đây chạy `npm run dev` trong container (dev server, không tối ưu
# và dễ rò HMR); giờ build production đúng chuẩn.

FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED 1
ARG ATE_BACKEND_URL
ARG NEXT_PUBLIC_ATE_API_ORIGIN
ENV ATE_BACKEND_URL=$ATE_BACKEND_URL
ENV NEXT_PUBLIC_ATE_API_ORIGIN=$NEXT_PUBLIC_ATE_API_ORIGIN
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV production
ENV NEXT_TELEMETRY_DISABLED 1
# next.config set output:'standalone' (ngoài Vercel) -> chạy trực tiếp server.js
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
ENV PORT 3000
ENV HOSTNAME "0.0.0.0"
CMD ["node", "server.js"]
