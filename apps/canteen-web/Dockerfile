# Staff dashboard image. Build from the repository root:
#   docker build -f apps/canteen-web/Dockerfile -t canteen-web .
FROM node:24-alpine AS build
WORKDIR /web
COPY apps/canteen-web/package.json apps/canteen-web/package-lock.json ./
RUN npm ci
COPY apps/canteen-web/ ./
RUN npm test && npm run build

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY apps/canteen-web/nginx.conf /etc/nginx/conf.d/default.conf
COPY apps/canteen-web/security-headers.inc /etc/nginx/security-headers.inc
COPY --from=build /web/dist /usr/share/nginx/html
EXPOSE 8080
