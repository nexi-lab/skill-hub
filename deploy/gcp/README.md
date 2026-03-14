# GCP Deploy

This directory contains the first repeatable GCP deployment path for `skill-hub`.

This GCP path is an integration deployment for validating `skill-hub` against Nexus.
The preferred long-term production shape is still an independently managed Nexus runtime with `skill-hub` deployed alongside it.

Current target:

- one Compute Engine VM
- Docker Engine + Docker Compose on the VM
- the existing `compose.yaml` stack
- public access to `skill-hub` on port `8040`
- Nexus reachable only on the VM and Docker network

Files:

- `startup.sh`: bootstraps Docker on the VM
- `compose.gcp.yaml`: restart policy override for the Compose stack
- `compose.nexus-source.yaml`: source-build override that uses the Nexus repo root `Dockerfile`
- `deploy.sh`: creates or updates the VM, static IP, firewall rule, syncs the local repo to the VM, and starts the stack remotely

Default deployment settings:

- project: `nexi-lab-888`
- region: `us-central1`
- zone: `us-central1-a`
- instance: `skill-hub-vm`
- machine type: `e2-standard-4`
- Nexus deploy mode: `release`
- Nexus image: `ghcr.io/nexi-lab/nexus:0.9.2`

Run:

```bash
GCLOUD=/opt/homebrew/share/google-cloud-sdk/bin/gcloud \
PROJECT=nexi-lab-888 \
ZONE=us-central1-a \
bash deploy/gcp/deploy.sh
```

To deploy with a local Nexus source checkout instead of the released image wrapper:

```bash
GCLOUD=/opt/homebrew/share/google-cloud-sdk/bin/gcloud \
PROJECT=nexi-lab-888 \
ZONE=us-central1-a \
NEXUS_DEPLOY_MODE=source \
LOCAL_NEXUS_DIR=/absolute/path/to/nexus \
bash deploy/gcp/deploy.sh
```
