FROM node:26-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci --ignore-scripts

COPY . .

# the build number passed from the deploy
ARG BUILD_NUMBER
ARG PRIMEUI_LICENSE_KEY
ENV BUILD_NUMBER=$BUILD_NUMBER
ENV PRIMEUI_LICENSE_KEY=$PRIMEUI_LICENSE_KEY

RUN npm run build

FROM nginxinc/nginx-unprivileged:1.30-alpine

COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/snippets/ /etc/nginx/snippets/

EXPOSE 8080