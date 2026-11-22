FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci --omit=dev --ignore-scripts && \
    npm install --save-dev typescript tsx @types/node

COPY tsconfig.json ./
COPY src/ ./src/

RUN npm run build

CMD node dist/deploy-commands.js && node dist/index.js
