use std::path::PathBuf;

use anyhow::Error;

use structopt::StructOpt;

mod parser;
mod utils;

#[derive(Debug, StructOpt)]
#[structopt(
    name = "osm2rdf",
    about = "Imports and updates OSM data in an RDF database."
)]
pub struct Opt {
    /// Enable verbose output.
    #[structopt(short, long)]
    #[allow(dead_code)]
    verbose: bool,

    /// File to store node cache.
    #[structopt(short, long)]
    cache: PathBuf,

    #[structopt(subcommand)]
    cmd: Command,
}

#[derive(Debug, StructOpt)]
enum Command {
    /// Parses a PBF file into multiple .ttl.gz (Turtle files)
    Parse {
        /// Approximate maximum uncompressed file size, in MB, per output file.
        #[structopt(short, long, default_value = "100")]
        max_file_size: usize,
        /// Number of worker threads to run.
        #[structopt(short, long)]
        workers: Option<usize>,
        /// OSM input PBF file
        input_file: PathBuf,
        /// Output directory
        #[structopt(parse(try_from_str = parse_outdir))]
        output_dir: PathBuf,
    },
    // /// Download OSM incremental update files and store them as either TTL files or the RDF database.
    // Update {
    //     /// Start updating from this sequence ID. By default, gets it from RDF server.
    //     #[structopt(long)]
    //     seqid: Option<i64>,
    //     /// Source of the minute data.
    //     #[structopt(
    //         long,
    //         default_value = "https://planet.openstreetmap.org/replication/minute"
    //     )]
    //     updater_url: String,
    //     /// Maximum size in kB for changes to download at once
    //     #[structopt(long, default_value = "10240")]
    //     max_download: usize,
    //     /// Do not modify RDF database.
    //     #[structopt(short, long)]
    //     dry_run: bool,
    //     /// Approximate maximum uncompressed file size, in MB, per output file. Only used if destination is a directory.
    //     #[structopt(short, long, default_value = "100")]
    //     max_file_size: usize,
    //     /// Either a URL of the RDF database, or a directory with TTL files created with the "parse" command.
    //     #[structopt(default_value = "http://localhost:9999/bigdata/namespace/wdq/sparql")]
    //     destination: String,
    // },
}

// enum Foo {
//     /// Host URL to upload data. Default: %(default)s
//     #[structopt(
//     long,
//     default_value = "http://localhost:9999/bigdata/namespace/wdq/sparql"
//     )]
//     host: String,
// }

fn parse_outdir(path: &str) -> anyhow::Result<PathBuf> {
    let path = PathBuf::from(path);
    if path.is_dir() {
        Ok(path)
    } else {
        Err(Error::msg("Output directory does not exist"))
    }
}

fn main() -> anyhow::Result<()> {
    let opt: Opt = Opt::from_args();
    match opt.cmd {
        Command::Parse { .. } => parser::parse(opt),
    }
}
