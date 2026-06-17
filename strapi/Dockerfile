# Builds the Strapi orchestration app from ./strapi/app.
# Run ./strapi/init.sh once to scaffold the app + inject the content-types.
FROM node:20-alpine
RUN apk add --no-cache build-base python3 vips-dev
WORKDIR /opt/app
COPY app/package*.json ./
RUN npm install
COPY app/ ./
ENV NODE_ENV=production
RUN npm run build
EXPOSE 1337
CMD ["npm", "run", "start"]
