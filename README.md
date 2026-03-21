# Learn K3s on a PI

Toy project to learn how to deploy a web app with a database on a Raspberry Pi using K3s, Flux CD, and GitHub Actions.

## Architecture

```
GitHub repo
  |
  |-- PR opened -------> GitHub Actions (CI) --> Build image (verify only)
  |
  |-- PR merged to master --> GitHub Actions --> Build ARM64 image --> Push to GHCR
                                                                         |
                                                                    Flux CD (on Pi)
                                                                         |
                                                              Detects new image tag
                                                                         |
                                                              Updates deployment
                                                                         |
K3s cluster on Pi:                                                       |
  ┌──────────────────────────────────────────────────────┐               |
  │  Pod: hello-world (Flask + Gunicorn) <───────────────┼───────────────┘
  │    └── Env vars from Secret                          │
  │         │                                            │
  │         ▼                                            │
  │  Pod: postgresql                                     │
  │    └── Data persisted via PVC                        │
  │                                                      │
  │  Service: hello-world (NodePort 30080) ──► external  │
  │  Service: postgresql (ClusterIP) ──► internal only   │
  └──────────────────────────────────────────────────────┘
```

- **Web app**: Python Flask notes API served with Gunicorn
- **Database**: PostgreSQL 16 with persistent storage
- **Container**: Multi-arch Docker image (ARM64) hosted on GitHub Container Registry (GHCR)
- **Kubernetes**: K3s (single node) on Raspberry Pi, Traefik disabled
- **Exposure**: NodePort Service on port 30080
- **CI/CD**: GitHub Actions builds images, Flux CD (GitOps) handles deployment
- **No SSH required**: Flux runs inside the cluster and pulls updates autonomously

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web frontend |
| GET | `/api/notes` | List all notes (JSON), supports `?date=YYYY-MM-DD` filter |
| POST | `/api/notes` | Create a note (`{"title": "...", "content": "..."}`) |
| GET | `/api/notes/:id` | Get a note |
| PUT | `/api/notes/:id` | Update a note |
| DELETE | `/api/notes/:id` | Delete a note |
| GET | `/health` | Health check |

## Project Structure

```
app/
  main.py              # Flask notes API (CRUD + health)
  templates/
    index.html         # Web frontend
  requirements.txt     # Python dependencies
k8s/
  deployment.yaml      # App Deployment (with DB env vars from Secret)
  service.yaml         # App NodePort Service (port 30080)
  postgres-pvc.yaml    # Persistent storage for DB (1Gi)
  postgres-deployment.yaml  # PostgreSQL Deployment
  postgres-service.yaml     # PostgreSQL ClusterIP Service
  kustomization.yaml   # Kustomize resource list
  flux/
    image-repository.yaml    # Flux: watch GHCR for new images
    image-policy.yaml        # Flux: select image tags (timestamp-sha format)
    image-update-automation.yaml  # Flux: auto-update deployment manifest
.github/workflows/
  ci.yaml              # PR: build image (no push)
  deploy.yaml          # Merge to master: build and push image to GHCR
Dockerfile             # Python 3.12 slim + uv + Gunicorn
```

## Decisions

- **K3s installed without Traefik** (`--disable traefik`) because port 80 is already in use by `ppdl_main` on the Pi
- **NodePort on 30080** to avoid conflicts with existing services (22/sshd, 80/ppdl_main, 111/rpcbind, 631/cupsd, 5900/wayvnc)
- **Flux CD for deployment** instead of SSH — no need to expose the Pi to the internet. Flux runs inside K3s and pulls changes from Git/GHCR
- **PostgreSQL with PVC** — data persists across pod restarts. ClusterIP service keeps DB internal-only
- **DB credentials managed manually** — K8s Secret created directly on the Pi, not stored in Git
- **Branch protection on master**: PRs required with CI status check (`build` job must pass). Admin can bypass approval requirement for solo workflow
- **No direct pushes to master**: all changes go through PRs
- **Auto-delete branches** after PR merge
- **uv** instead of pip for faster Docker builds
- **Image tags** use `YYYYMMDDHHMMSS-shortsha` format for correct chronological ordering
- **Flux bootstrap** with `--token-auth` and `--read-write-key` for image automation write access

## Pi Setup

### 1. Install K3s (without Traefik)

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable traefik" sh -
```

### 2. Verify K3s is running

```bash
sudo k3s kubectl get nodes
```

### 3. Install Flux CLI

```bash
curl -s https://fluxcd.io/install.sh | sudo bash
```

### 4. Bootstrap Flux on the cluster

Export your GitHub personal access token (needs repo permissions):

```bash
export GITHUB_TOKEN=<your-token>
```

Bootstrap Flux (include image automation controllers, with write access):

```bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

flux bootstrap github \
  --owner=DragosHF \
  --repository=learn-k3s-pi \
  --branch=master \
  --path=./k8s \
  --personal \
  --components-extra=image-reflector-controller,image-automation-controller \
  --token-auth \
  --read-write-key
```

This will:
- Install Flux controllers in the cluster
- Configure Flux to watch the `k8s/` directory for manifests
- Commit Flux system manifests to the repo

### 5. Create the database credentials secret

```bash
sudo k3s kubectl create secret generic postgres-credentials \
  --from-literal=POSTGRES_DB=notes \
  --from-literal=POSTGRES_USER=notes \
  --from-literal=POSTGRES_PASSWORD=your-secure-password
```

This secret is referenced by both the app and PostgreSQL pods. It is not stored in Git.

## GitHub Setup

### Secrets

No secrets required for deployment. Flux pulls from GHCR and Git autonomously.

`GITHUB_TOKEN` is automatically available in GitHub Actions for pushing to GHCR.

### Branch Protection (master)

| Rule | Value |
|------|-------|
| Require pull request | Yes |
| Required approvals | 1 (admin can bypass) |
| Require `build` status check | Yes |
| Branch must be up to date | Yes |
| Force pushes | Blocked |
| Branch deletion | Blocked |

## Usage

1. Create a feature branch
2. Make changes and push
3. Open a PR to `master`
4. CI builds the image to verify it compiles
5. Merge the PR
6. GitHub Actions builds and pushes the image to GHCR
7. Flux detects the new image tag and updates the deployment
8. Access the app at `http://<pi-ip>:30080`

### Example API Usage

```bash
# Create a note
curl -X POST http://<pi-ip>:30080/api/notes \
  -H "Content-Type: application/json" \
  -d '{"title": "First note", "content": "Hello from K3s!"}'

# List all notes
curl http://<pi-ip>:30080/api/notes

# Filter notes by date
curl http://<pi-ip>:30080/api/notes?date=2026-03-21

# Get a specific note
curl http://<pi-ip>:30080/api/notes/1

# Update a note
curl -X PUT http://<pi-ip>:30080/api/notes/1 \
  -H "Content-Type: application/json" \
  -d '{"content": "Updated content"}'

# Delete a note
curl -X DELETE http://<pi-ip>:30080/api/notes/1
```

## Web Frontend

The app includes a web UI at `http://<pi-ip>:30080` with:

- Create, edit, and delete notes
- Timestamps (created/updated) on each note
- Calendar widget to filter notes by date
