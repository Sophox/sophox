# Sophox container

Containerizing Sophox.org (WIP)

## Usage

1.  Install [Docker](https://www.docker.com/community-edition) and [Docker Compose](https://docs.docker.com/compose/install/)
2.  Change the `POSTGRES_USER` and `POSTGRES_PASSWORD` in the `.env` file
3.  In your terminal run `docker-compose up`
4.  Visit http://localhost:8080

## Implementation Progress

- [x] Postgres database service
- [x] Wikidata Query RDF backend service (http://localhost:8080/bigdata)
- [x] Wikidata Query GUI frontend service (http://localhost:8080)
- [x] Nginx proxy for services
- [x] Mapshaper service
- [x] OSM Regions service (http://localhost:8080/regions)
- [ ] SSL certificate generation
- [ ] `/sandbox`
- [ ] `/store`
- [ ] Script to load OSM database
- [ ] Script to load Wikdata
