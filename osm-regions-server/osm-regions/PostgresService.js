const postgres = require(`pg-promise`);

class PostgresService {

  /**
   * @param {Object} opts
   * @param {string} opts.host
   * @param {int} opts.port
   * @param {string} opts.database
   * @param {string} opts.user
   * @param {string} opts.password
   * @param {Object} [opts.requester]
   * @param {Object} [opts.queries]
   * @param {string} opts.queries.regularQuery
   * @param {string} opts.queries.noWaterQuery
   */
  constructor(opts) {
    this._regularQuery = opts.queries.regularQuery;
    this._noWaterQuery = opts.queries.noWaterQuery;
    this._requester = opts.requester;
    if (!this._requester) {
      const pgp = postgres();
      this._requester = pgp({
        host: opts.host,
        port: opts.port,
        database: opts.database,
        user: opts.user,
        password: opts.password
      });
    }
  }

  /**
   * Query geojson rows from Postgres
   * @param {string} table
   * @param {string[]} ids
   * @param {{waterTable:string}} [opts]
   * @returns {{id:int, data:string}[]}
   */
  query(table, ids, opts) {
    if (ids.length === 0) return [];

    let query = this._regularQuery;
    const params = [table, ids];
    if (opts && opts.waterTable) {
      query = this._noWaterQuery;
      params.push(opts.waterTable);
    }

    return this._requester.query(query, params);
  }

  /**
   * Convert rows into a proper GeoJSON string
   * @param {{id:int, data:string}[]} rows
   * @param {object} [properties]
   */
  static toGeoJSON(rows, properties) {
    const featuresStr = rows.map(row => {
      const propStr = JSON.stringify((properties && properties[row.id]) || {});
      return `{"type":"Feature","id":"${row.id}","properties":${propStr},"geometry":${row.data}}`;
    }).join(`,`);
    return `{"type":"FeatureCollection","features":[${featuresStr}]}`;
  }
}

module.exports = {PostgresService};
