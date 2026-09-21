# Frontend en dos etapas: nada se instala en la máquina del usuario, todo ocurre aquí dentro.

# ── 1) Compilación ────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app

# `npm ci` contra el package-lock.json versionado: la imagen se construye con las MISMAS versiones
# siempre. El lock se generó dentro de un contenedor, así que tenerlo no obliga a nadie a instalar
# npm en su máquina.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY tsconfig*.json vite.config.ts index.html ./
COPY src/ ./src/
RUN npm run build

# ── 2) Servicio ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
