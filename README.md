# Sophox

## Installation

Full planet Sophox should be installed on a sufficiently large (40+ GB RAM, 1TB Disk) server, preferably SSD NVMe disk.  In case of Google Cloud, a local SSD scratch disk is also recommended.  Use environment variables to override what data gets loaded.  See also the [Development section](#development) below.

The server must have `bash`, `docker`, `curl`, and `git`.  Everything else is loaded inside docker containers.

When cloning, make sure you get submodules (e.g. `git submodule update --init --recursive`)

### Google Cloud
* Create a `custom-6-39936` VM (6 vCPUs, 36GB RAM) or better with a 15GB boot disk, and attach a 1TB Persisted SSD disk.
* Set VM startup script to the following line, and the service should be ready in two to three days.  Insert any env var overrides right before, e.g. `export SOPHOX_HOST=example.org; curl ... | bash`
```
curl --silent --show-error --location --compressed https://raw.githubusercontent.com/Sophox/sophox/master/docker/startup.gcp.sh | bash
```

* You can view Traefik's dashboard with statistics and configuration at http://localhost:8080 by creating a tunnel to the VM instance (adjust VM name and zone):
```
$ gcloud compute ssh sophox-instance --zone=us-central1-b  -- -L 8080:localhost:8080
```

* To monitor the startup process, ssh into the server and view the startup script output:
```
sudo journalctl -u google-startup-scripts.service
```

### Monitoring
* See docker statistics:  `docker stats`
* View docker containers:  `docker ps`
* See individual docker's log:  `docker logs <container-id>` _(ID can be just the first few digits)_
* localhost:8080 shows Traefik's configuration and statistics.

## Automated Installation Steps
These steps are done automatically by the startup scripts. Many of the steps create empty `status` files in the `data/status` directory, indicating that a specific step is complete. This prevents full rebuild when the server is restarted.

##### [startup.sh](docker/startup.sh)
* If `DATA_DEV` is set, format and mount it as `DATA_DIR`.  Same applies to the optional `TEMP_DEV` + `TEMP_DIR`. _(e.g. `/dev/sdb`  as `/mnt/disks/data`, and `/dev/nvme0n1` as `/mnt/disks/temp`)_
* Clone/pull Sophox git repo _(Use `REPO_URL` and `REPO_BRANCH` to override. Set `REPO_URL` to "-" to disable)_
* Generate random Postgres password
* Download OSM dump file and validate md5 sum. (creates _status/file.downloaded_)
* Initialize Osmosis state configuration / timestamp
* Compile Blazegraph from [/wikidata-query-rdf](wikidata-query-rdf)  (creates _status/blazegraph.build_)
* Run docker containers with [docker-compose.yml](docker/docker-compose.yml)

## Development

Clone the repo with submodules.

If you have commit access to the Sophox repository, make sure to run this in order to automatically use ssh instead of https for submodules.
```
git config --global url.ssh://git@github.com/.insteadOf https://github.com/
```

For quick testing, you may want to use [docker/startup.local.sh](docker/startup.local.sh) to get Sophox locally and with a small OSM file.   Use  http://sophox.localhost  to browse it. You may need to add `127.0.0.1   sophox.localhost` to your `hosts` file.

You can also override some of the parameters by creating a file in the docker directory, e.g. docker/_belize.sh with similar content. Make sure the filename begins with an underscore (ignored by git):

```bash
#!/usr/bin/env bash
OSM_FILE=belize-latest.osm.pbf
OSM_FILE_URL=http://download.geofabrik.de/central-america/belize-latest.osm.pbf
MAX_MEMORY_MB=4000
source "$(dirname "$0")/startup.local.sh"
```

#### Notes for Mac users
* Make sure to set MAX_MEMORY_MB, because `free` util is not available.
