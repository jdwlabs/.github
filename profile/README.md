# jdwlabs

Self-hosted platform engineering lab: production K8s infrastructure, real app workloads, and a living portfolio of GitOps & full-stack practices.

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
| [platform](https://github.com/jdwlabs/platform) | Tenant-centric GitOps platform — ArgoCD, Vault, cert-manager, ESO, and CNPG |
| [deployments](https://github.com/jdwlabs/deployments) | Helm charts and ArgoCD ApplicationSet configs for the jdwlabs tenant |
| [apps](https://github.com/jdwlabs/apps) | Multi-language Nx monorepo — Angular frontends, Go services, Java Spring Boot backends |

---

**Maintainer:** [Jake Willmsen](https://github.com/jdwillmsen)
