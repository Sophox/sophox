FROM node:10.11-alpine
LABEL maintainer='Nick Peihl <nick.peihl@elastic.co>, Yuri Astrakhan <YuriAstrakhan@gmail.com>'

WORKDIR /app

COPY package*.json ./

# Git is needed at the moment because package.json relies on nyurik/osm-regions github repo (TODO)
RUN apk add --no-cache git && \
    npm install -g -s --no-progress yarn && \
    yarn && \
    yarn cache clean

COPY . .

EXPOSE 9978
CMD [ "yarn", "start" ]
