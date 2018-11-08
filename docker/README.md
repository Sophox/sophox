# Sophox

Instructions for setting up Sophox in Google Cloud

* Create a VM and a persistent disk
* Initialize persistent disk (adapted from [Google instructions](https://cloud.google.com/compute/docs/disks/add-persistent-disk#formatting))
```bash
$ sudo lsblk # Verify that the persistent disk is attached as /dev/sdb

$ sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/sdb
$ sudo mkdir -p /mnt/disks/data
$ sudo mount -o discard,defaults /dev/sdb /mnt/disks/data/
$ sudo chmod a+w /mnt/disks/data/
```

* VM should have this string as a startup script:
 `curl https://raw.githubusercontent.com/Sophox/sophox/master/docker/startup.sh | bash`
 
# Dashboard
* You can view Traefik's dashboard at http://localhost:8080 by creating a tunnel to the VM instance (adjust VM name and zone):
```
$ gcloud compute ssh sophox-instance --zone=us-central1-b  -- -L 8080:localhost:8080
```
