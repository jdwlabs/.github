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

## Layers

The lab is split into four layers. Each has one job, and a layer can change without the layers above it noticing.

```mermaid
flowchart TD
    subgraph tenants["Per tenant: jdwlabs · jdwillmsen · dotablaze-tech"]
        apps["<b>Applications</b>\nthe software being built"]
        delivery["<b>Delivery</b>\neach tenant's GitOps desired state"]
    end
    platform["<b>Platform</b>\nsecurity baseline every tenant inherits, plus shared services"]
    infra["<b>Infrastructure</b>\ncontrol plane that provisions compute and clusters on any hardware"]

    apps -->|"images"| delivery
    delivery -->|"runs on"| platform
    platform -->|"runs on"| infra
```

| Layer | Job | Repo |
|-------|-----|------|
| Infrastructure | The lab's own cloud provider: provisions compute and clusters on whatever hardware is underneath | [infrastructure](https://github.com/jdwlabs/infrastructure) |
| Platform | The managed layer, comparable to a managed Kubernetes service: a security baseline every tenant inherits (scoped access, pod security, network policy, quotas) plus shared services such as databases, storage, certificates, secrets, monitoring and alerting | [platform](https://github.com/jdwlabs/platform) |
| Delivery | What a tenant runs, declared in Git and kept apart from application code | [deployments](https://github.com/jdwlabs/deployments) for the jdwlabs tenant |
| Applications | The software being built; it produces images and never deploys itself | [apps](https://github.com/jdwlabs/apps) for the jdwlabs tenant |

The platform hosts other tenants alongside jdwlabs, each with its own delivery and application repos: [jdwillmsen](https://github.com/jdwillmsen) and [dotablaze-tech](https://github.com/dotablaze-tech).

The apps repo also holds the [AI SRE relay](https://github.com/jdwlabs/apps/tree/main/apps/backend/ai-sre-relay), a Go service that runs an LLM investigation on each Alertmanager alert and tracks the alert as a ticket until it resolves.

---

**Maintainer:** [Jake Willmsen](https://github.com/jdwillmsen)
