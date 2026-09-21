# syntax=docker/dockerfile:1.7
# Frontend en dos etapas: nada se instala en la máquina del usuario, todo ocurre aquí dentro.

# ── 1) Compilación ────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app

# `npm ci` contra el package-lock.json versionado: la imagen se construye con las MISMAS versiones
# siempre. El lock se generó dentro de un contenedor, así que tenerlo no obliga a nadie a instalar
# npm en su máquina.
#
# El `--mount=type=cache` guarda los tarballs de npm ENTRE construcciones. Sin él, `npm ci` borra
# node_modules y vuelve a bajarlo todo de la red cada vez que cambia el lock; con él, solo se
# descarga lo que de verdad es nuevo. `--prefer-offline` le dice a npm que mire ahí primero.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm ci --prefer-offline --no-audit --no-fund

# Después del install: editar un componente no puede invalidar la capa de dependencias.
COPY --link tsconfig.json tsconfig.app.json tsconfig.node.json vite.config.ts index.html ./
COPY --link src/ ./src/
RUN npm run build

# ── 2) Servicio ───────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine
COPY --link nginx.conf /etc/nginx/conf.d/default.conf
COPY --link --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
