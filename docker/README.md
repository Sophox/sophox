# Sophox

Instructions for setting up Sophox in Google Cloud

* Create a VM and a persistent disk (e.g. use Terraform)
* VM should have this string as a startup script:
 `curl https://raw.githubusercontent.com/Sophox/sophox/master/docker/startup.sh | bash`
 
# Dashboard
* You can view Traefik's dashboard at http://localhost:8080 by creating a tunnel to the VM instance (adjust VM name and zone):
```
$ gcloud compute ssh sophox-instance --zone=us-central1-b  -- -L 8080:localhost:8080
```
