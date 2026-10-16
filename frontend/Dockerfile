FROM node:22-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# the build number passed from the deploy
ARG BUILD_NUMBER
ENV BUILD_NUMBER=$BUILD_NUMBER

RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30-alpine

COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/snippets/ /etc/nginx/snippets/

EXPOSE 8080