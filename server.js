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

// Allowed params (per topojson code)
const NUMERIC_PARAMS = {
  // 'planarArea': { 'desc': 'minimum planar triangle area (absolute)' },
  // 'planarQuantile': { 'desc': 'minimum planar triangle area (quantile)', max: 1 },
  'sphericalArea': {'desc': 'minimum spherical excess (absolute)'},
  'sphericalQuantile': {'desc': 'minimum spherical excess (quantile)', max: 1},
};

function parseParams(req) {

  const sparql = req.query.sparql;
  if (!sparql) {
    throw new MyError(400, `bad sparql parameter`);
  }

  const type = req.params.type;
  if (type !== `geojson.json` && type !== `topojson.json`) {
    throw new MyError(400, `bad type parameter. Allows "geojson.json" and "topojson.json"`);
  }

  let param, value;
  for (const name of Object.keys(NUMERIC_PARAMS)) {
    if (req.query.hasOwnProperty(name)) {
      if (param) {
        throw new Error(`${name} parameter cannot be used together with ${param}`);
      }
      value = parseFloat(req.query[name]);
      const info = NUMERIC_PARAMS[name];
      param = name;
      if (!(value.toString() === req.query[name] && value >= 0 && value <= (info.max || Number.MAX_VALUE))) {
        throw new Error(`${name} parameter, ${info.desc}, must be a non-negative number` +
          (info.max ? ` not larger than ${info.max}` : ''));
      }
    }
  }

  const filter = req.params.filter;
  if (filter !== undefined && filter !== `all` && filter !== `detached`) {
    throw new MyError(400, `bad filter parameter. Allows "all" and "detached"`);
  }

  return {sparql, param, value, type, filter};
}

async function processQueryRequest(req, resp) {
  let {sparql, param, value, type, filter} = parseParams(req);

  const qres = await sparqlService.query(sparql, `id`);
  const pres = await postgresService.query(secrets.table, Object.keys(qres));
  let result = PostgresService.toGeoJSON(pres, qres);

  console.log(new Date().toISOString(), type, param || 'noSimpl', value || 0, filter || 'noFilter', result.length, req.headers[`x-real-ip`], sparql);

  if (param || type === `topojson.json`) {

    result = topojson.topology({data: JSON.parse(result)}, {
      // preserve all properties
      'property-transform': feature => feature.properties
    });

    if (param) {
      const system = (param === 'sphericalArea' || param === 'sphericalQuantile') ? `spherical` : `planar`;

      result = topojson.presimplify(result, topojson[system + `TriangleArea`]);

      if (param === 'planarQuantile' || param === 'sphericalQuantile') {
        value = topojson.quantile(result, value);
        param = system + `Area`;
        res.header(`X-Equivalent-${param}`, value.toString());
      }

      result = topojson.simplify(result, value);

      if (filter) {
        const filterFunc = filter === 'all' ? topojson.filterWeight : topojson.filterAttachedWeight;
        result = topojson.filter(result, filterFunc(result, value, topojson[system + `RingArea`]));
      }

      const transform = result.transform;
      if (transform) {
        result = topojson.quantize(result, transform);
      }

      if (type === `geojson.json`) {
        result = topojson.feature(result, result.objects.data);
      }
    }
  }

  const contentType = type === 'geojson.json' ? 'application/geo+json' : 'application/topo+json';

  resp.status(200).type(contentType).send(result);
}
