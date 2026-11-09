# Two stages: Node builds the app, then only the built files go into a small
# nginx image. Node, node_modules and the source code are not in the result

# Stage 1: build the React app into plain HTML, CSS and JavaScript files
FROM node:26-alpine AS build

WORKDIR /app

# Packages before the code, so this layer stays cached until they change.
# npm ci installs exactly what package-lock.json says
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: serve the files from stage 1
FROM nginx:1.29-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
