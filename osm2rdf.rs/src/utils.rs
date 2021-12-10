use chrono::{TimeZone, Utc};
use json::JsonValue;
use percent_encoding::{utf8_percent_encode, AsciiSet, CONTROLS};
use regex::Regex;

pub(crate) trait StringExt {
    fn push_str_value(&mut self, predicate: &'static str, value: &str);
    fn push_quoted_str(&mut self, value: &str);
    fn push_char_value(&mut self, predicate: &'static str, value: char);
    fn push_bool_value(&mut self, predicate: &'static str, value: bool);
    fn push_int_value(&mut self, predicate: &'static str, value: i64);
    fn push_date_value(&mut self, predicate: &'static str, value: i64);
    fn push_point(&mut self, predicate: &'static str, latitude: f64, longitude: f64);
    fn push_wiki_url(&mut self, lang: &str, site: &str, title: &str);
    fn push_tag(&mut self, key: &str, value: &str, utils: &Consts);
    fn push_metadata(&mut self, version: i32, user: &str, milli_timestamp: i64, changeset: i64);
}

impl StringExt for String {
    fn push_str_value(&mut self, predicate: &'static str, value: &str) {
        self.push_str(predicate);
        self.push(' ');
        self.push_quoted_str(value);
    }

    fn push_quoted_str(&mut self, value: &str) {
        // TODO: optimize?
        self.push_str(&JsonValue::from(value).dump());
        self.push_str(";\n");
    }

    fn push_char_value(&mut self, predicate: &'static str, value: char) {
        self.push_str(predicate);
        self.push_str(" \"");
        self.push(value);
        self.push_str("\";\n");
    }

    fn push_bool_value(&mut self, predicate: &'static str, value: bool) {
        self.push_str(predicate);
        self.push_str(" \"");
        self.push_str(if value { "true" } else { "false" });
        self.push_str("\"^^xsd:boolean;\n");
    }

    fn push_int_value(&mut self, predicate: &'static str, value: i64) {
        self.push_str(predicate);
        self.push_str(" \"");
        self.push_str(&value.to_string());
        self.push_str("\"^^xsd:integer;\n");
    }

    fn push_date_value(&mut self, predicate: &'static str, milli_timestamp: i64) {
        // "{0:%Y-%m-%dT%H:%M:%S}Z"^^xsd:dateTime
        self.push_str(predicate);
        self.push_str(" \"");
        self.push_str(&format_ts(milli_timestamp));
        self.push_str("\"^^xsd:dateTime;\n");
    }

    fn push_point(&mut self, predicate: &'static str, latitude: f64, longitude: f64) {
        self.push_str(predicate);
        self.push_str(" \"Point(");
        self.push_str(&longitude.to_string());
        self.push(' ');
        self.push_str(&latitude.to_string());
        self.push_str(")\"^^geo:wktLiteral");
        self.push_str(";\n");
    }

    fn push_wiki_url(&mut self, lang: &str, site: &str, title: &str) {
        self.push_str("<https://");
        self.push_str(lang);
        self.push_str(site);
        self.extend(utf8_percent_encode(
            title.replace(' ', "_").as_str(),
            PERCENT_ENC_SET,
        ));
        self.push('>');
        self.push_str(";\n");
    }

    fn push_tag(&mut self, key: &str, value: &str, consts: &Consts) {
        if !consts.re_simple_local_name.is_match(key) {
            // Record any unusual tag name in a "osmm:badkey" statement
            self.push_str_value("osmm:badkey", value);
            return;
        }

        self.push_str("osmt:");
        self.push_str(key);
        self.push(' ');
        let mut parsed = false;
        if key.contains("wikidata") {
            if consts.re_wikidata_value.is_match(value) {
                self.push_str("wd:");
                self.push_str(value);
                parsed = true;
            } else if consts.re_wikidata_multi_value.is_match(value) {
                for v in value.split(';') {
                    self.push_str("wd:");
                    self.push_str(v);
                    self.push(',');
                }
                self.pop(); // remove trailing ","
                parsed = true;
            }
        } else if key.contains("wikipedia") {
            if let Some(v) = consts.re_wikipedia_value.captures(value) {
                self.push_wiki_url(
                    v.get(1).unwrap().as_str(),
                    ".wikipedia.org/wiki/",
                    v.get(2).unwrap().as_str(),
                );
                parsed = true;
            }
        }
        if !parsed {
            self.push_quoted_str(value);
        }
    }

    fn push_metadata(&mut self, version: i32, user: &str, milli_timestamp: i64, changeset: i64) {
        self.push_int_value("osmm:version", version as i64);
        self.push_str_value("osmm:user", user);
        self.push_date_value("osmm:timestamp", milli_timestamp);
        self.push_int_value("osmm:changeset", changeset);
        self.pop();
        self.pop();
        self.push_str(".\n");
    }
}

pub fn format_ts(milli_timestamp: i64) -> String {
    format!(
        "{:?}",
        Utc.timestamp(milli_timestamp / 1000, (milli_timestamp % 1000) as u32)
    )
}

pub const PERCENT_ENC_SET: &AsciiSet = &CONTROLS
    .add(b';')
    .add(b'@')
    .add(b'$')
    .add(b'!')
    .add(b'*')
    .add(b'(')
    .add(b')')
    .add(b',')
    .add(b'/')
    .add(b'~')
    .add(b':')
    // The "#" is also safe - used for anchoring
    .add(b'#');

#[derive(Clone, Debug)]
pub struct Consts {
    pub re_simple_local_name: Regex,
    pub re_wikidata_key: Regex,
    pub re_wikidata_value: Regex,
    pub re_wikidata_multi_value: Regex,
    pub re_wikipedia_value: Regex,
}

impl Consts {
    pub fn new() -> Self {
        Consts {
            /// Total length of the maximum "valid" local name is 60 (58 + first + last char)
            /// Local name may contain letters, numbers anywhere, and -:_ symbols anywhere except first and last position
            re_simple_local_name: Regex::new(r"^[0-9a-zA-Z_]([-:0-9a-zA-Z_]{0,58}[0-9a-zA-Z_])?$")
                .unwrap(),

            re_wikidata_key: Regex::new(r"(.:)?wikidata$").unwrap(),
            re_wikidata_value: Regex::new(r"^Q[1-9][0-9]{0,18}$").unwrap(),
            re_wikidata_multi_value: Regex::new(r"^Q[1-9][0-9]{0,18}(;Q[1-9][0-9]{0,18})+$")
                .unwrap(),
            re_wikipedia_value: Regex::new(r"^([-a-z]+):(.+)$").unwrap(),
        }
    }
}

#[derive(Clone, Default, Debug)]
pub struct Stats {
    pub added_nodes: u64,
    pub added_rels: u64,
    pub added_ways: u64,
    pub skipped_nodes: u64,
    pub deleted_nodes: u64,
    pub deleted_rels: u64,
    pub deleted_ways: u64,
    pub blocks: u64,
}

impl Stats {
    pub(crate) fn combine(&mut self, other: Stats) {
        self.added_nodes += other.added_nodes;
        self.added_rels += other.added_rels;
        self.added_ways += other.added_ways;
        self.skipped_nodes += other.skipped_nodes;
        self.deleted_nodes += other.deleted_nodes;
        self.deleted_rels += other.deleted_rels;
        self.deleted_ways += other.deleted_ways;
        self.blocks += 1;
    }
}

#[derive(Debug)]
pub enum Statement {
    Skip,
    Delete {
        elem: Element,
        id: i64,
    },
    Create {
        elem: Element,
        id: i64,
        ts: i64,
        val: String,
    },
}

#[derive(Debug)]
pub enum Element {
    Node,
    Way,
    Relation,
}
