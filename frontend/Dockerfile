FROM node:20-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build
ENV PORT=3700
EXPOSE 3700
CMD ["npm", "run", "start"]
