'use strict';

const compression = require(`compression`);
const {SparqlService, PostgresService} = require(`osm-regions/src`);
const app = require(`express`)();
const secrets = require(`./secrets`);
const topojson = require(`topojson`);

const port = 9978;
// const rdfServerUrl = `https://sophox.org/bigdata/sparql`;
const rdfService = `https://sophox.org/bigdata/namespace/wdq/sparql`;

// app.use(function (req, res, next) {
//   res.header(`Access-Control-Allow-Origin`, `*`);
//   res.header(`Access-Control-Allow-Methods`, `GET`);
//   res.header(`Access-Control-Allow-Headers`, `Content-Type, Content-Length`);
//   next();
// });

app.options(`/*`, function (req, res) {
  res.sendStatus(200);
});

app.use(compression());

app.get(`/regions/:type`, handleRequest);

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
    await processQueryRequest(req, resp);
  } catch (err) {
    if (err instanceof MyError) {
      resp.status(err.code).send(`\n\n${err.msg}\n\n`);
    } else {
      resp.status(500).send(`\n\nboom\n\n`);
    }
    try {
      if (err instanceof MyError) {
        console.error(err.msg, JSON.stringify(req.params), JSON.stringify(req.query));
      } else {
        console.error(err, JSON.stringify(req.params), JSON.stringify(req.query));
      }
    } catch (e2) {
      console.error(err);
    }
  }
}

async function processQueryRequest(req, resp) {
  const sparql = req.query.sparql;
  if (!sparql) {
    throw new MyError(400, `bad sparql parameter`);
  }

  const type = req.params.type;
  if (type !== `geojson.json` && type !== `topojson.json`) {
    throw new MyError(400, `bad type parameter`);
  }

  const qres = await sparqlService.query(sparql, `id`);

  const pres = await postgresService.query(secrets.table, Object.keys(qres));

  let result = PostgresService.toGeoJSON(pres);

  switch (type) {
  case `geojson.json`:
    resp.status(200).type(`application/geo+json`).send(result);
    break;

  case `topojson.json`:

    result = topojson.topology({data: JSON.parse(result)}, {
      // preserve all properties
      "property-transform": feature => feature.properties
    });
    result = JSON.stringify(result);

    resp.status(200).type(`application/topo+json`).send(result);
    break;

  default:
    throw new Error();
  }

  console.log(type, result.length, sparql);
}
