FROM node:18-slim

WORKDIR /app
ENV NODE_ENV=development

COPY package.json package-lock.json ./
RUN npm ci

# Copy the entire Next.js project (must include /app routes)
COPY . .

EXPOSE 3000
CMD ["npm","run","dev","--","--hostname","0.0.0.0","--port","3000"]
