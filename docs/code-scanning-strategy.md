# Code Scanning & Quality Tooling Strategy

Evaluation for JDWLABS-71: a free/OSS-only code-scanning stack across the
polyglot jdwlabs monorepos (Go, Kotlin/Java Spring Boot, TypeScript/Angular,
Python, shell, Terraform, Helm, Kubernetes manifests, Dockerfiles).

## Baseline (already in place)

- **CodeQL** — running on `apps` only. Covers TS/JS and Java (Kotlin/Spring
  Boot) well; Go support exists but is shallower; no coverage for
  Terraform/Helm/k8s/Dockerfiles/shell (not in CodeQL's scope).
- **Dependabot** — active on `apps` (version + security updates).
- **Secret scanning + push protection** — free on public repos; jdwlabs repos
  are public, so this should already be on org-wide. Verify per-repo in
  Settings > Code security (not scriptable via this PR — a settings check,
  not a workflow).

## Comparison matrix

| Tool | Covers | GitHub integration | Hosting | Maintenance | License |
|---|---|---|---|---|---|
| CodeQL | SAST: TS/JS, Java strong; Go partial | Native, SARIF to Security tab | GitHub-hosted | Low (GH-managed) | Free (public repos) |
| Dependabot | SCA (lockfile CVEs + version PRs) | Native | GitHub-hosted | Low | Free |
| GH secret scanning + push protection | Secrets | Native | GitHub-hosted | Low | Free (public repos) |
| **Trivy** | SCA (Go/npm/gradle lockfiles) + IaC misconfig (Terraform/Helm/k8s) + Dockerfile misconfig + secrets | SARIF via `codeql-action/upload-sarif` | Self-run in CI (no server) | Low — single static binary, no self-hosted service | Apache-2.0 |
| Semgrep OSS | SAST, broad language support incl. Go/Kotlin/TS | SARIF upload or Semgrep Cloud free tier (public repos) | Self-run in CI, or free SaaS | Low-medium (rule tuning over time) | LGPL-2.1 (engine), rules mixed |
| SonarQube Community Edition | SAST + quality/duplication metrics | PR decoration limited on CE; SARIF not first-class on CE | Self-host (needs a running server) | **High** — persistent service, DB, upgrades | LGPL/Community |
| SonarQube Cloud (SaaS) | Same as above | Native PR decoration | SaaS, free for public repos | Low | Free tier |
| tfsec / Checkov / KICS | Terraform-specific IaC | SARIF upload | Self-run in CI | Low, but overlaps Trivy's misconfig scanner | Apache/OSS |
| kube-linter / Kubescape | K8s manifest misconfig | SARIF upload | Self-run in CI | Low, overlaps Trivy | Apache-2.0 |
| hadolint | Dockerfile lint | SARIF upload | Self-run in CI | Low, overlaps Trivy's Dockerfile scanner | GPL-3.0 |
| gitleaks | Secrets (git-history aware) | SARIF upload | Self-run in CI | Low | MIT |
| OSV-Scanner | SCA, cross-ecosystem | SARIF upload | Self-run in CI | Low, overlaps Trivy's vuln scanner | Apache-2.0 |

## Recommendation

**Layer 1 (GitHub-native, keep as-is, extend to all repos):** CodeQL,
Dependabot, secret scanning + push protection. Extending CodeQL from `apps`
to `platform`/`infrastructure`/`deployments` is a repo-by-repo
`codeql.yml` addition (follow-up ticket — Go/shell-heavy repos get less value
from CodeQL than `apps` does, so sequence `apps`-like repos first).

**Layer 2 (one new tool, not five):** **Trivy**, filesystem mode, covering
SCA + IaC misconfig + Dockerfile misconfig + secrets in a single pass. It
directly covers the parts of this org's stack CodeQL doesn't reach —
Terraform, Helm, Kubernetes manifests, Dockerfiles — with one dependency
instead of stitching together tfsec + kube-linter + hadolint + gitleaks
separately. Lower maintenance burden than running four narrow tools, and
zero infrastructure (a single static binary in the CI runner, no service to
operate).

**Not recommended (for now):**

- **Semgrep OSS** — real SAST value (esp. Go, which CodeQL covers only
  partially), but adds a second SAST engine with its own rule-tuning
  overhead on top of CodeQL. Revisit as a follow-up once Trivy is rolled out
  org-wide and there's a concrete gap Semgrep would close (e.g. a Go-specific
  vulnerability class CodeQL misses).
- **tfsec / Checkov / KICS / kube-linter / Kubescape / hadolint / gitleaks /
  OSV-Scanner individually** — all subsumed by Trivy's fs-mode scanners for
  this stack. Not worth the added workflow surface unless Trivy's coverage
  proves insufficient for a specific artifact type.
- **SonarQube (self-host or SaaS)** — **not recommended.** Self-hosting a
  Community Edition instance means running a persistent service (+ DB) on
  the jdwlabs k8s cluster, which has a documented history of CI-adjacent OOM
  incidents (JDWLABS-37, JDWLABS-57 — ARC runner pods already contend for
  memory on undersized workers). Adding a always-on SonarQube service is
  exactly the kind of extra cluster load that history argues against. The
  SaaS free tier avoids that, but CE's PR decoration and SARIF support are
  limited enough that it wouldn't cleanly feed the same GitHub Security tab
  aggregation point as everything else in this stack. Skip both; revisit
  only if a specific quality-metric need (duplication, complexity trends)
  emerges that Trivy/CodeQL don't address.

## PoC

`security-scan.yml` (this PR) — a reusable `workflow_call` workflow running
Trivy in fs mode (`vuln,misconfig,secret` scanners) and uploading SARIF via
`github/codeql-action/upload-sarif`. Wired into the `apps` repo's CI as a
non-blocking job (`fail-on-findings: false`) so results land in the Security
tab without gating merges yet.

## Rollout plan

1. **This PR** — reusable workflow + PoC wired into `apps` (non-blocking).
2. Wire the same reusable workflow into `platform`, `infrastructure`,
   `deployments` (follow-up tickets, one per repo — each has different
   scan-path considerations, e.g. `infrastructure`'s Talos machine-config
   templates aren't plain YAML, see JDWLABS-57's fork notes on
   `worker.yaml` needing template rendering before static analysis).
3. Extend CodeQL to the other 3 repos (separate follow-up, GitHub-native,
   no new tooling).
4. After a burn-in period with `fail-on-findings: false` across all repos
   (confirm the finding volume is real signal, not noise), flip to
   `fail-on-findings: true` for CRITICAL/HIGH and consider adding the Trivy
   scan job as a required status check in each repo's ruleset (out of scope
   for this ticket — JDWLABS-63 already modified the `apps` Baseline
   ruleset separately; don't touch it again here).
5. Semgrep OSS evaluation as a follow-up only if a concrete Go/Kotlin SAST
   gap is identified after Trivy + CodeQL are both running for a while.

## Evaluated on paper only (not run)

SonarQube CE/Cloud, Semgrep OSS, tfsec, Checkov, KICS, kube-linter,
Kubescape, hadolint, gitleaks, OSV-Scanner — ruled out or deferred per the
recommendation above without a hands-on run, since Trivy's fs-mode scanners
cover the same ground for this stack. If any of these get revisited, verify
against the actual repo content before adopting (this doc's judgment calls
are based on published tool docs + this org's stack, not a live trial of
each).
