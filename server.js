'use strict';

const compression = require(`compression`);
const {SparqlService, PostgresService} = require(`osm-regions/src`);
const app = require(`express`)();
const secrets = require(`./secrets`);
const topojson = require(`topojson`);

const port = 9978;
// const rdfServerUrl = `https://sophox.org/bigdata/sparql`;
const rdfService = `https://sophox.org/bigdata/namespace/wdq/sparql`;

app.use(function (req, res, next) {
  res.header(`Access-Control-Allow-Origin`, `*`);
  res.header(`Access-Control-Allow-Methods`, `GET`);
  res.header(`Access-Control-Allow-Headers`, `Content-Type, Content-Length`);
  next();
});

app.use(compression());

app.get(`/`, handleRequest);

const sparqlService = new SparqlService({
  url: rdfService,
  userAgent: `osm-regions`,
  Accept: `application/sparql-results+json`
});

const postgresService = new PostgresService({
  host: secrets.host,
  port: secrets.port,
  database: secrets.database,
  user: secrets.user,
  password: secrets.password,
});

app.listen(port, err => {
  if (err) {
    console.error(err);
  } else {
    console.log(`server is listening on ${port}`);
  }
});

class MyError extends Error {
  constructor(code, msg) {
    super();
    this.code = code;
    this.msg = msg;
  }
}

async function handleRequest(req, resp) {
  try {

    const sparql = req.query.sparql;

    const qres = await sparqlService.query(sparql);

    const pres = await postgresService.query(secrets.table, Object.keys(qres));

    let result = PostgresService.toGeoJSON(pres);

    if (req.query.topojson) {
      result = topojson.topology({data: JSON.parse(result)}, {
        // preserve all properties
        "property-transform": feature => feature.properties
      });
      result = JSON.stringify(result);
    }

    resp.status(201).type(`application/vnd.geo+json`).send(result);

  } catch (err) {
    if (err instanceof MyError) {
      resp.status(err.code).send(err.msg);
    } else {
      resp.status(500).send(`boom`);
    }
    try {
      if (err instanceof MyError) {
        console.error(err.msg, JSON.stringify(req.params), JSON.stringify(req.body));
      } else {
        console.error(err, JSON.stringify(req.params), JSON.stringify(req.body));
      }
    } catch (e2) {
      console.error(err);
    }
  }
}
