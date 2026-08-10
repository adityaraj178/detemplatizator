# ArgoCD PR Impact Analyser

A tool that performs **pre-merge impact analysis** for GitOps pull requests. When a PR is raised against a deployment repository (Helm or Kustomize), this tool spins up a lightweight ephemeral environment, fully expands the manifests for both the source and target branches, computes a YAML diff, and reports which ArgoCD applications and namespaces are affected — before the PR is merged.

---

## What it does

```
PR raised on Bitbucket
        │
        ▼
1. Parse PR  ──► extract source branch, target branch, repo URLs
        │
        ▼
2. Deploy vcluster  ──► lightweight isolated k8s cluster inside host cluster
        │
        ▼
3. Deploy ArgoCD  ──► lightweight ArgoCD instance inside vcluster
        │
        ▼
4. Hydrate TARGET branch  ──► deploy manifests from target branch → sync → expand
        │
        ▼
5. Hydrate SOURCE branch  ──► deploy manifests from source branch → sync → expand
        │
        ▼
6. Compute diff  ──► compare expanded manifests (normalised YAML diff)
        │
        ▼
7. Report impact  ──► which apps changed, which namespaces affected
        │
        ▼
8. Post comment  ──► diff posted back to the Bitbucket PR as a comment
```

---

## Module overview

| File | Responsibility |
|---|---|
| `home.py` | Orchestrator — reads env/input, calls all modules in sequence |
| `entrypoint.sh` | Docker entrypoint — creates the vcluster then launches `home.py` |
| `pr.py` | Parses a Bitbucket PR URL to extract branches, repos, and PR metadata |
| `in_source.py` | Fetches the root `application.yaml` from Bitbucket raw API; extracts target revision and namespace |
| `test_deploy_app.py` | Deploys the ArgoCD app manifests into the vcluster and connects to it |
| `target_hydration.py` | Syncs the target/source branch apps in ArgoCD and expands (hydrates) the full manifests |
| `in_consolidate_backup.py` | Consolidates all hydrated app manifests into a single YAML for diffing |
| `diff3.py` | Normalises and diffs two sets of YAML manifests; produces `diff3_output.diff` |
| `pr_comment.py` | Posts the diff as a comment on the Bitbucket PR |
| `fix.py` | Creates the vcluster bearer token and retrieves the ArgoCD admin password |
| `kill_port.py` | Frees port 8080 before port-forwarding ArgoCD |

---

## Prerequisites

- A Kubernetes host cluster (the vcluster runs inside it)
- `kubectl` configured with access to the host cluster
- Docker (to build and run the container)
- A Bitbucket account with an App Password that has read access to the deployment repo

The Dockerfile installs all other dependencies (`oc`, `argocd` CLI, `vcluster`, `kind`, Python packages).

---

## Configuration

All secrets and environment-specific values are passed as environment variables — nothing is hardcoded.

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `BB_USERNAME` | Bitbucket username |
| `BB_APP_PASSWORD` | Bitbucket App Password (read access to deployment repo) |
| `BITBUCKET_BASE_URL` | Base URL of your Bitbucket instance (e.g. `https://bitbucket.example.net`) |
| `OC_URL` | OpenShift/Kubernetes API server URL |
| `OC_TOKEN` | Service account bearer token for the host cluster |
| `OC_NAMESPACE` | Namespace on the host cluster where the vcluster is created |
| `OC_HTTPS_PROXY` | HTTPS proxy (if required by your network) |
| `PR_URL` | Full Bitbucket PR URL to analyse |
| `RAW_URL` | Raw URL of the root `application.yaml` in Bitbucket |

When running interactively (`python home.py`), `PR_URL`, `RAW_URL`, and the host cluster name are prompted at the terminal.

---

## Running with Docker

### Build

```bash
docker build -t pr-impact-analyser .
```

### Run

```bash
docker run --rm \
  -e BB_USERNAME=<your-username> \
  -e BB_APP_PASSWORD=<your-app-password> \
  -e OC_URL=<cluster-api-url> \
  -e OC_TOKEN=<bearer-token> \
  -e OC_NAMESPACE=<namespace> \
  -e OC_HTTPS_PROXY=<proxy-url> \
  -e PR_URL=<bitbucket-pr-url> \
  -e RAW_URL=<raw-application-yaml-url> \
  pr-impact-analyser
```

Or load from your `.env` file:

```bash
docker run --rm --env-file .env pr-impact-analyser
```

---

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

export BB_USERNAME=...
export BB_APP_PASSWORD=...
# ... set remaining variables ...

python home.py
```

You will be prompted interactively for the PR URL, raw URL, and host cluster name.

---

## Output

- **`diff3_output.diff`** — raw YAML diff between the fully-expanded source and target branch manifests
- **Bitbucket PR comment** — the diff is posted directly onto the PR so reviewers can see the impact inline
- **Console output** — lists which ArgoCD application names and namespaces are affected

---

## How the impact analysis works

1. **Parse** the PR to find the source branch (the incoming changes) and the target branch (what it merges into).
2. **Fetch** the root ArgoCD `application.yaml` to discover the app tree and target namespace.
3. **Spin up a vcluster** — an isolated virtual Kubernetes cluster inside the host cluster — so the analysis never touches any real environment.
4. **Deploy ArgoCD** inside the vcluster and register the Bitbucket repo credentials as ArgoCD secrets.
5. **Hydrate the target branch**: point ArgoCD at the target branch, trigger a sync, then collect the fully-rendered Kubernetes manifests for every application.
6. **Hydrate the source branch**: repeat the same process for the PR's source branch.
7. **Normalise and diff**: strip dynamic fields (resource versions, sync timestamps, etc.) and produce a deterministic YAML diff. Only meaningful configuration changes surface — not noisy metadata churn.
8. **Report**: the diff is written to `diff3_output.diff` and posted as a comment on the PR.

---

## Security notes

- Never commit `.env` or real credentials — `.gitignore` excludes `.env` and certificate files.
- All credentials are injected at runtime via environment variables or Kubernetes secrets.
- The vcluster is ephemeral and isolated; it does not affect any production or staging environment.
- Rotate your `OC_TOKEN` and `BB_APP_PASSWORD` regularly; treat them as short-lived credentials.
