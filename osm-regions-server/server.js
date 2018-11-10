'use strict';

const compression = require(`compression`);
const {SparqlService, PostgresService, directQueries} = require(`osm-regions/src`);
const app = require(`express`)();
const topojson = require(`topojson`);

const port = 9978;

// app.use(function (req, resp, next) {
//   resp.header(`Access-Control-Allow-Origin`, `*`);
//   resp.header(`Access-Control-Allow-Methods`, `GET`);
//   resp.header(`Access-Control-Allow-Headers`, `Content-Type, Content-Length`);
//   next();
// });

app.options(`/*`, function (req, resp) {
  resp.sendStatus(200);
});

app.use(compression());

app.get(`/regions/:format`, handleRequest);

const sparqlSvcOpts = {
  userAgent: `osm-regions`,
  Accept: `application/sparql-results+json`,
};
const wikibaseSparqlService = new SparqlService({url: process.env.WIKIBASE_URL, ...sparqlSvcOpts});
const sophoxSparqlService = new SparqlService({url: process.env.SOPHOX_URL, ...sparqlSvcOpts});

const pgServerOpts = {
  queries: directQueries,
  host: process.env.POSTGRES_HOST,
  database: process.env.POSTGRES_DB,
  user: process.env.POSTGRES_USER,
  password: process.env.POSTGRES_PASSWORD,
};

if (process.env.POSTGRES_PORT) {
  pgServerOpts.port = process.env.POSTGRES_PORT;
}

const postgresService = new PostgresService(pgServerOpts);

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
  // 'planarArea': { desc: 'minimum planar triangle area (absolute)' },
  // 'planarQuantile': { desc: 'minimum planar triangle area (quantile)', max: 1 },
  sphericalArea: {desc: `minimum spherical excess (absolute)`},
  sphericalQuantile: {desc: `minimum spherical excess (quantile)`, max: 1},
};

const parseNumber = function (params, name, info) {
  const value = parseFloat(params[name]);
  if (!(value >= 0 && value <= (info.max || Number.MAX_VALUE))) {
    throw new Error(`${name} parameter, ${info.desc}, must be a non-negative number${
      info.max ? ` not larger than ${info.max}` : ``}`);
  }
  return value;
};

function parseParams(req) {
  const params = {...req.query, format: req.params.format};

  if ((params.ids === undefined) === (params.sparql === undefined)) {
    throw new MyError(400, `Either "ids" or "query" parameter must be given, but not both`);
  }

  let sparqlService;
  if (params.sparql) {
    switch (params.service) {
      case undefined:
      case 'sophox':
        sparqlService = sophoxSparqlService;
        break;
      case 'wikidata':
        sparqlService = wikibaseSparqlService;
        break;
      default:
        throw new MyError(400, `If set, "service" param must be either "sophox" or "wikidata"`);
    }
  } else {
    throw new MyError(400, `Parameter "service" must be used with "sparql"`);
  }

  let ids = params.ids;
  if (ids !== undefined) {
    ids = ids.split(`,`).filter(id => id !== ``);
    if (ids.length > 1000) throw new MyErorr(400, `No more than 1000 IDs is allowed`);
    ids.forEach(val => {
      if (!/^Q[1-9][0-9]{0,15}$/.test(val)) throw new MyError(400, `Invalid Wikidata ID`);
    });
  }

  const format = params.format;
  if (format !== `geojson.json` && format !== `topojson.json`) {
    throw new MyError(400, `bad format parameter. Allows "geojson.json" and "topojson.json"`);
  }

  let simplifyCmd, value;
  for (const name of Object.keys(NUMERIC_PARAMS)) {
    if (params.hasOwnProperty(name)) {
      if (simplifyCmd) {
        throw new Error(`${name} parameter cannot be used together with ${simplifyCmd}`);
      }
      simplifyCmd = name;
      value = parseNumber(params, name, NUMERIC_PARAMS[name]);
    }
  }

  // By default, without any params, optimize the result to a fraction of the original.
  // To preserve the original geometry, set sphericalQuantile=1
  if (!simplifyCmd) {
    simplifyCmd = `sphericalQuantile`;
    value = 0.07;
  } else if (simplifyCmd === `sphericalQuantile` && value === 1) {
    simplifyCmd = undefined;
    value = undefined;
  }

  let filter = params.filter;
  if (filter === undefined) {
    filter = simplifyCmd ? `all` : `none`;
  } else if (filter !== `none` && filter !== `all` && filter !== `detached`) {
    throw new MyError(400, `bad filter parameter. Allows "none", "all" and "detached"`);
  }

  let quantize = simplifyCmd ? 4 : 0;
  if (params.hasOwnProperty(`quantize`)) {
    quantize = parseNumber(params, `quantize`, {desc: `Exponent to use for quantizing`, max: 8});
  }
  quantize = quantize ? Math.pow(10, quantize) : 0;

  const postgresOpts = {}; // { waterTable: process.env.OSM_REGIONS_SQL_WATER_TABLE };

  return {ids, sparqlService, sparql: params.sparql, simplifyCmd, value, quantize, format, filter, postgresOpts};
}

async function processQueryRequest(req, resp) {
  let {sparqlService, sparql, ids, simplifyCmd, value, quantize, format, filter, postgresOpts} = parseParams(req);
  let newValue = value;
  let equivLog = ``;
  let qres;

  if (sparql) {
    qres = await sparqlService.query(sparql, `id`);
    ids = Object.keys(qres);
  }
  const pres = await postgresService._query(process.env.REGIONS_TABLE, ids, postgresOpts);
  let result = PostgresService.toGeoJSON(pres, qres);
  const originalSize = result.length;

  if (simplifyCmd || format === `topojson.json`) {

    result = topojson.topology({data: JSON.parse(result)}, quantize);

    if (simplifyCmd) {
      const system = (simplifyCmd === `sphericalArea` || simplifyCmd === `sphericalQuantile`) ? `spherical` : `planar`;

      result = topojson.presimplify(result, topojson[`${system  }TriangleArea`]);

      if (simplifyCmd === `planarQuantile` || simplifyCmd === `sphericalQuantile`) {
        newValue = topojson.quantile(result, newValue);
        resp.header(`X-Equivalent-${system}Area`, newValue.toString());
        equivLog = `X-Equivalent-${system}Area=${newValue.toString()}`;
      }

      result = topojson.simplify(result, newValue);

      if (filter !== `none`) {
        const filterFunc = filter === `all` ? topojson.filterWeight : topojson.filterAttachedWeight;
        result = topojson.filter(result, filterFunc(result, newValue, topojson[`${system  }RingArea`]));
      }

      // if (quantize) {
      //   result = topojson.quantize(result, quantize);
      // }

      if (format === `geojson.json`) {
        result = topojson.feature(result, result.objects.data);
      }
    }
  }

  const contentType = format === `geojson.json` ? `application/geo+json` : `application/topo+json`;

  resp.setHeader(`Cache-Control`, `public, max-age=43200`);
  resp.status(200).type(contentType).send(result);

  console.log(`\n*************${new Date().toISOString()} ${format} ${simplifyCmd || 'noSimpl'}=${value || 0} filter=${filter} ${equivLog} quantize=${quantize} size=${originalSize}=>${(typeof result === 'string' ? result : JSON.stringify(result)).length} ip=${req.headers['x-real-ip']}\n${sparql}`);

}
