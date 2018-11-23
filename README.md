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

### Hetzner or similar server

We have a machine with 12, 128GB RAM, and 3 SSDs: 2 small ones and a 1.8TB one.

* Using [robot UI](https://robot.your-server.de/), rescue reboot with a public key, and apply firewall template "Webserver". Reboot.
* `ssh root@<IP>`
* run `installimage`
* Choose -ubuntu 18.04
* In the config file, comment out the 3rd (large) disk, set `SWRAIDLEVEL 1`, and hit `F10`.  After done formatting, use `shutdown -r now` to reboot.
* `ssh root@88.99.164.208` and run:
```bash
# Install utils and docker
apt update && apt upgrade
apt-get install -y apt-transport-https ca-certificates curl git software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -

# You may need to use "bionic" instead of `lsb_release ...` 
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

apt-cache policy docker-ce
apt update && apt-get install -y docker-ce

# Format and mount the large disk, and make it auto-mount.  We use xfs, but ext4 is fine too.
mkdir -p /mnt/data && mount -o discard,defaults /dev/sdc /mnt/data
echo UUID=`blkid -s UUID -o value /dev/sdc` /mnt/data xfs discard,defaults,nofail 0 2 | tee -a /etc/fstab
```

* Install Sophox:
```
export DATA_DIR=/mnt/data
export REPO_BRANCH=master
nohup curl --fail --silent --show-error --location --compressed \
   https://raw.githubusercontent.com/Sophox/sophox/${REPO_BRANCH}/docker/startup.planet.sh \
   | bash >> /mnt/data/startup.log 2>&1 &
```

### Monitoring
* See docker statistics:  `docker stats`
* View docker containers:  `docker ps`
* See individual docker's log:  `docker logs <container-id>` _(ID can be just the first few digits)_
* `localhost:8080` shows Traefik's configuration and statistics.

## Automated Installation Steps
These steps are done automatically by the startup scripts. Many of the steps create empty `status` files in the `data/status` directory, indicating that a specific step is complete. This prevents full rebuild when the server is restarted.

##### [startup.sh](docker/startup.sh)
* If `DATA_DEV` is set, format and mount it as `DATA_DIR`.  Same applies to the optional `TEMP_DEV` + `TEMP_DIR`. _(e.g. `/dev/sdb`  as `/mnt/disks/data`, and `/dev/nvme0n1` as `/mnt/disks/temp`)_
* Clone/pull Sophox git repo _(Use `REPO_URL` and `REPO_BRANCH` to override. Set `REPO_URL` to "-" to disable)_
* Generate random Postgres password
* Download OSM dump file and validate md5 sum. (creates _status/file.downloaded_)
* Initialize Osmosis state configuration / timestamp
* Compile Blazegraph from [/wikidata-query-rdf](wikidata-query-rdf)  (creates _status/blazegraph.build_)
* Start PostgreSQL and Blazegraph with [dc-databases.yml](docker/dc-databases.yml) and wait for them to activate
* Run [dc-importers.yml](docker/dc-importers.yml) to parse downloaded file into RDF TTL files and into Postgres tables. The TTL files are then imported into Blazegraph.  This step runs without the `--detach`, and should take a few days to complete.  Running it a second time should not take any time. Note that if it crashes, you may have to do some manual cleanup steps (e.g. wipe it all clean)
* Run [dc-updaters.yml](docker/dc-updaters.yml) and [dc-services.yml](docker/dc-services.yml). Updaters will update OSM data -> PostgreSQL tables (geoshapes), OSM data->Blazegraph, and OSM Wiki->Blazegraph. 

## Development

Clone the repo with submodules.

If you have commit access to the Sophox repository, make sure to run this in order to automatically use ssh instead of https for submodules.
```
git config --global url.ssh://git@github.com/.insteadOf https://github.com/
```

For quick testing, you may want to use [docker/startup.local.sh](docker/startup.local.sh) to get Sophox locally and with a small OSM file.   Use  http://sophox.localhost  to browse it. You may need to add `127.0.0.1   sophox.localhost` to your `hosts` file.

To disable some of the services, create these files in the status dir:
* `osm-rdf.disabled` - disable OSM data into Blazegraph parser/importer/updater
* `osm-pgsql.disabled` - disable OSM data into PostgreSQL importer/updater
* `wikibase.disabled` - disable OSM Wikibase into Blazegraph updater

You can also override some of the parameters by creating a file in the docker directory, e.g. docker/_belize.sh with similar content. Make sure the filename begins with an underscore (ignored by git):

```bash
#!/usr/bin/env bash

OSM_FILE=belize-latest.osm.pbf
OSM_FILE_URL=http://download.geofabrik.de/central-america/belize-latest.osm.pbf
MAX_MEMORY_MB=4000

current_dir=$(dirname "$0")
status_dir="${current_dir}/../_data_dir/status/"
mkdir -p "${status_dir}"

# touch "${status_dir}/osm-rdf.disabled"
# touch "${status_dir}/osm-pgsql.disabled"
# touch "${status_dir}/wikibase.disabled"

source "${current_dir}/startup.local.sh"
```


#### Notes for Mac users
* Make sure to set MAX_MEMORY_MB, because `free` util is not available.
