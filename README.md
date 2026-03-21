# Learn K3s on a PI

Toy project to learn how to deploy a basic web app on a Raspberry Pi using K3s, Flux CD, and GitHub Actions.

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
                                                              App live at :30080
```

- **Web app**: Python Flask "Hello World" served with Gunicorn
- **Container**: Multi-arch Docker image (ARM64) hosted on GitHub Container Registry (GHCR)
- **Kubernetes**: K3s (single node) on Raspberry Pi, Traefik disabled
- **Exposure**: NodePort Service on port 30080
- **CI/CD**: GitHub Actions builds images, Flux CD (GitOps) handles deployment
- **No SSH required**: Flux runs inside the cluster and pulls updates autonomously

## Project Structure

```
app/
  main.py              # Flask app (/ and /health endpoints)
  requirements.txt     # Python dependencies
k8s/
  deployment.yaml      # Kubernetes Deployment manifest
  service.yaml         # Kubernetes NodePort Service (port 30080)
  flux/
    image-repository.yaml    # Flux: watch GHCR for new images
    image-policy.yaml        # Flux: select image tags (git SHA format)
    image-update-automation.yaml  # Flux: auto-update deployment manifest
.github/workflows/
  ci.yaml              # PR: build image (no push)
  deploy.yaml          # Merge to master: build and push image to GHCR
Dockerfile             # Python 3.12 slim + Gunicorn
```

## Decisions

- **K3s installed without Traefik** (`--disable traefik`) because port 80 is already in use by `ppdl_main` on the Pi
- **NodePort on 30080** to avoid conflicts with existing services (22/sshd, 80/ppdl_main, 111/rpcbind, 631/cupsd, 5900/wayvnc)
- **Flux CD for deployment** instead of SSH — no need to expose the Pi to the internet. Flux runs inside K3s and pulls changes from Git/GHCR
- **Branch protection on master**: PRs required with CI status check (`build` job must pass). Admin can bypass approval requirement for solo workflow
- **No direct pushes to master**: all changes go through PRs

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

Bootstrap Flux:

```bash
flux bootstrap github \
  --owner=DragosHF \
  --repository=learn-k3s-pi \
  --branch=master \
  --path=./k8s \
  --personal
```

This will:
- Install Flux controllers in the cluster
- Configure Flux to watch the `k8s/` directory for manifests
- Commit Flux system manifests to the repo

### 5. Install Flux image automation controllers

```bash
flux install --components-extra=image-reflector-controller,image-automation-controller
```

### 6. Apply the Flux image automation manifests

```bash
sudo k3s kubectl apply -f k8s/flux/
```

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
