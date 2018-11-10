FROM node:10.11-alpine
LABEL maintainer='Nick Peihl <nick.peihl@elastic.co>'

# RUN mkdir -p /app
WORKDIR /app

COPY package*.json ./

#RUN apk add --no-cache git \
#    && npm install
#
RUN npm install -g -s --no-progress yarn && \
    yarn && \
    yarn cache clean

COPY . .

EXPOSE 9978
CMD [ "yarn", "start" ]
