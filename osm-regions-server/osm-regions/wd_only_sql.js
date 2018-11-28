/**
 * Force all geometries to be the same winding order (for some reason they are not in DB)
 * Join them all in a single row.
 */
const SQL_QUERY_PREFIX = `SELECT wikidata as id,
 ST_AsGeoJSON(ST_Transform(ST_ForceRHR(way), 4326)) as data FROM
(
  SELECT wikidata, ST_Multi(ST_Union(`;

const SQL_QUERY_SUFFIX = `)) AS way
  FROM (
    SELECT wikidata, way
    FROM $1~
    WHERE wikidata IN ($2:csv)
    ) tbl1
  GROUP BY wikidata
) tbl2`;

module.exports = {

  regularQuery: `${SQL_QUERY_PREFIX}way${SQL_QUERY_SUFFIX}`,

  noWaterQuery: `${SQL_QUERY_PREFIX}
COALESCE(ST_Difference(
  tbl1.way,
  (select ST_Union(water.way) from $3~ water where ST_Intersects(tbl1.way, water.way))
), tbl1.way)
${SQL_QUERY_SUFFIX}`

};
