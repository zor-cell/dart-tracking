FROM node:22-alpine AS build
WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

# The build counter shown in the app; the deploy passes its build number, and a
# build without it labels itself a local one.
ARG APP_BUILD
ENV APP_BUILD=$APP_BUILD

RUN npm run build

FROM nginx:1.25-alpine

COPY --from=build /app/dist/frontend/browser /usr/share/nginx/html
COPY default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80