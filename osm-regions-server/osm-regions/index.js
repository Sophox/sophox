module.exports = {
  ...require(`./SparqlService`),
  ...require(`./PostgresService`),
  directQueries: require(`./wd_only_sql`),
  hstoreQueries: require(`./wd_in_hstore_sql`),
};

