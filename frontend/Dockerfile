FROM node:18-slim

WORKDIR /app
ENV NODE_ENV=development
ARG BUILD_SHA=dev
ENV NEXT_PUBLIC_BUILD_SHA=$BUILD_SHA

COPY package.json package-lock.json ./
RUN npm ci
# Ensure Playwright browser deps are present for local runs.
RUN npx playwright install-deps
RUN npx playwright install chromium

# Copy the entire Next.js project (must include /app routes)
COPY . .

EXPOSE 3000
CMD ["npm","run","dev","--","--hostname","0.0.0.0","--port","3000"]
