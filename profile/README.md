# jdwlabs

Self-hosted platform engineering lab: Kubernetes infrastructure, a GitOps platform, and the applications that run on it.

![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?logo=kubernetes&logoColor=white)
![ArgoCD](https://img.shields.io/badge/ArgoCD-EF7B4D?logo=argo&logoColor=white)
![Talos](https://img.shields.io/badge/Talos-FF7300?logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-7B42BC?logo=terraform&logoColor=white)
![Vault](https://img.shields.io/badge/Vault-FFEC6E?logo=vault&logoColor=black)
![Angular](https://img.shields.io/badge/Angular-DD0031?logo=angular&logoColor=white)
![Go](https://img.shields.io/badge/Go-00ADD8?logo=go&logoColor=white)
![Java](https://img.shields.io/badge/Java-ED8B00?logo=openjdk&logoColor=white)
![Nx](https://img.shields.io/badge/Nx-143055?logo=nx&logoColor=white)

---

## Mission

The lab is run to the standard a paying customer's workloads would need: bare-metal provisioning, GitOps delivery, and application services, built and operated with the same rigor as a production shop.

**What "done" means here:**

- Every change ships through a reviewed, green-CI pull request. Nothing is pushed directly to `main`.
- A GitOps change isn't done at green CI; it's done when ArgoCD reports the workload **Synced + Healthy** against the live cluster.
- Docs are code: paths and structure claimed in a README must resolve in the repo, or it's a bug, not a typo to shrug off.

The [org-wide code standards](https://github.com/jdwlabs/.github/blob/main/docs/code-standards.md) spell out the full contract this repo map exists to enforce.

---

## The Stack

```mermaid
flowchart TD
    infra["<b>infrastructure</b>\nTalos · Proxmox · Terraform · talops"]
    platform["<b>platform</b>\nArgoCD · Vault · cert-manager · ESO · CNPG"]
    deployments["<b>deployments</b>\nHelm charts · ArgoCD ApplicationSet"]
    apps["<b>apps</b>\nAngular · Go · Java · Nx monorepo"]

    infra -->|"provisions cluster"| platform
    platform -->|"manages tenant namespaces"| deployments
    deployments -->|"deploys workloads from"| apps
```

## Repositories

| Repo | Description |
|------|-------------|
| [infrastructure](https://github.com/jdwlabs/infrastructure) | Talos Kubernetes cluster provisioning on Proxmox via Terraform and the `talops` CLI |
| [platform](https://github.com/jdwlabs/platform) | Tenant-centric GitOps platform: ArgoCD, Vault, cert-manager, ESO, and CNPG |
| [deployments](https://github.com/jdwlabs/deployments) | Helm charts and ArgoCD ApplicationSet configs for the jdwlabs tenant |
| [apps](https://github.com/jdwlabs/apps) | Multi-language Nx monorepo: Angular frontends, Go services, Java Spring Boot backends |

The apps repo also holds the [AI SRE relay](https://github.com/jdwlabs/apps/tree/main/apps/backend/ai-sre-relay), a Go service that runs an LLM investigation on each Alertmanager alert and tracks the alert as a ticket until it resolves.

---

**Maintainer:** [Jake Willmsen](https://github.com/jdwillmsen)
