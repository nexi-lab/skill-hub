# GCP Deploy

This directory contains the first repeatable GCP deployment path for `skill-hub`.

Current target:

- one Compute Engine VM
- Docker Engine + Docker Compose on the VM
- the existing `compose.yaml` stack
- public access to `skill-hub` on port `8040`
- Nexus reachable only on the VM and Docker network

Files:

- `startup.sh`: bootstraps Docker, clones `nexi-lab/skill-hub`, and starts the stack
- `compose.gcp.yaml`: restart policy override for the Compose stack
- `deploy.sh`: creates or updates the VM, static IP, and firewall rule

Default deployment settings:

- project: `nexi-lab-888`
- region: `us-central1`
- zone: `us-central1-a`
- instance: `skill-hub-vm`
- machine type: `e2-standard-4`

Run:

```bash
GCLOUD=/opt/homebrew/share/google-cloud-sdk/bin/gcloud \
PROJECT=nexi-lab-888 \
ZONE=us-central1-a \
bash deploy/gcp/deploy.sh
```
