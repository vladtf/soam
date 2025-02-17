FROM node:18-alpine

WORKDIR /app

# Copy dependency files and install dependencies
COPY package*.json ./
RUN npm install --legacy-peer-deps

COPY . .

RUN npm run build

EXPOSE 3000

CMD ["npm", "run", "dev"]
