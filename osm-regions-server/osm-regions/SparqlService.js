const preq = require(`preq`);
const parseWikidataValue = require(`wd-type-parser`);

class SparqlService {

  constructor(opts) {
    if (!opts.url) throw new Error(`SparqlService url is not set`);
    if (!opts.userAgent) throw new Error(`SparqlService userAgent is not set`);

    this._endpoint = opts.url || `https://query.wikidata.org/bigdata/namespace/wdq/sparql`;
    this._headers = {
      'User-Agent': opts.userAgent,
      Accept: `application/sparql-results+json`,
    };
    this._requester = opts.requester || preq.get;
    this._normalizeIdOnly = opts.normalizeIdOnly;
  }

  async query(query, idColumn) {

    const queryResult = await this._requester({
      uri: this._endpoint,
      query: {format: `json`, query: query},
      headers: this._headers
    });

    if (!queryResult.headers[`content-type`].startsWith(`application/sparql-results+json`)) {
      throw new Error(`Unexpected content type ${ queryResult.headers[`content-type`]}`);
    }

    const data = queryResult.body;
    if (!data.results || !Array.isArray(data.results.bindings)) {
      throw new Error(`SPARQL query result does not have "results.bindings"`);
    }

    const useDefaultIdColumn = !idColumn;
    if (!useDefaultIdColumn) idColumn = `id`;

    const result = {};
    for (const wd of data.results.bindings) {
      if (!(idColumn in wd)) {
        let msg = `SPARQL query result does not contain ${JSON.stringify(idColumn)} column.`;
        if (useDefaultIdColumn) {
          msg += ` Custom ID column was not specified.`;
        }
        throw new Error(msg);
      }

      const value = wd[idColumn];
      const id = value.type !== `uri` ? false : parseWikidataValue(value, true);
      if (!id) {
        throw new Error(
          `SPARQL query result id column ${JSON.stringify(idColumn)} is expected to be a valid Wikidata ID`);
      } else if (result.hasOwnProperty(id)) {
        throw new Error(`SPARQL query result contains non-unique ID ${JSON.stringify(id)}`);
      }

      delete wd[idColumn];

      if (!this._normalizeIdOnly) {
        for (const k of Object.keys(wd)) {
          wd[k] = parseWikidataValue(wd[k]);
        }
      }

      result[id] = wd;
    }

    return result;
  }
}

module.exports = {SparqlService};
