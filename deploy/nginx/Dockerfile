# 阶段：前端构建 + Nginx（静态资源与 /api 反向代理的单入口镜像）
# 构建上下文为仓库根目录（依赖 frontend/ 源码与 deploy/nginx 配置）

# ---- 前端构建 ----
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- 运行镜像 ----
FROM nginx:1.27-alpine
COPY --from=frontend-build /build/dist /usr/share/nginx/html
COPY deploy/nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
