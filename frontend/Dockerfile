# Frontend en dos etapas: nada se instala en la máquina del usuario, todo ocurre aquí dentro.

# ── 1) Compilación ────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app

# `npm install` y no `npm ci`: no se versiona un package-lock.json, precisamente para que nadie
# tenga que ejecutar npm en local para generarlo.
COPY package.json ./
RUN npm install --no-audit --no-fund

COPY tsconfig*.json vite.config.ts index.html ./
COPY src/ ./src/
RUN npm run build

# ── 2) Servicio ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
