# Build stage
FROM node:20-alpine AS build

WORKDIR /app

# Copy both packages
COPY animal-island-ui/ animal-island-ui/
COPY frontend/ frontend/

# Build animal-island-ui
WORKDIR /app/animal-island-ui
RUN npm ci && npm run build

# Build frontend
WORKDIR /app/frontend
RUN npm ci && VITE_API_BASE_URL=/api npx vite build

# Production stage
FROM nginx:alpine
COPY --from=build /app/frontend/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
