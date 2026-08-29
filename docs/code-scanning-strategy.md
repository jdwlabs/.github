# Code Scanning & Quality Tooling Strategy

Evaluation for JDWLABS-71: a free/OSS-only code-scanning stack across the
polyglot jdwlabs monorepos (Go, Kotlin/Java Spring Boot, TypeScript/Angular,
Python, shell, Terraform, Helm, Kubernetes manifests, Dockerfiles).

> **This is a point-in-time evaluation, not a description of current CI.**
> What `security-scan.yml` runs today — its jobs, which of them block, its
> inputs, and which repositories call it — is documented in
> [`.github/workflows/README.md`](../.github/workflows/README.md), which is the
> single owner of that contract. This document records how the tooling choice
> was made and deliberately does not restate it; an earlier second copy of the
> job list drifted three ways before anyone noticed.

## Baseline (at time of evaluation)

- **CodeQL** — running on `apps` only, via GitHub's default setup rather than a
  checked-in workflow. Covers TS/JS and Java (Kotlin/Spring Boot) well; Go
  support exists but is shallower; no coverage for
  Terraform/Helm/k8s/Dockerfiles/shell (not in CodeQL's scope).
  *Since then:* moved to a checked-in advanced-setup workflow — see
  "Decision: CodeQL advanced setup, not default setup" below.
- **Dependabot** — described here as active on `apps` for version and security
  updates. *Since then:* version updates consolidated onto **Renovate** (a
  `renovate.json` per repo plus an org-level default). Dependabot vulnerability
  alerts remain enabled; its automated security fixes are not. That split is
  deliberate — see below.
- **Secret scanning + push protection** — free on public repos, and every
  jdwlabs repo is public, so this was assumed to be on org-wide. The assumption
  was recorded here as something to verify, and was not: checked 2026-07-29,
  both were disabled on all five repositories. Enabling them is a repository
  setting, not a workflow change, and is tracked separately. A CI secrets gate
  is not a substitute for push protection, which rejects the push itself rather
  than failing a pull request after the fact.

### Decision: Renovate remediates, Dependabot only detects

Dependabot's **automated security fixes** stay disabled; its **vulnerability
alerts** stay enabled. Verified 2026-07-30 on all five repositories:
`automated-security-fixes` reports `enabled=false`, `vulnerability-alerts`
returns `204` (enabled).

The reasoning follows the ownership rule the org-wide Renovate preset
(`default.json`) already states for dependency automation generally:

> Renovate is the single owner of dependency automation in this org;
> repository-level (UI) Dependabot should remain disabled so updates arrive
> through one reviewable pipeline.

Security work is not an exception to that ownership, because the preset already
exempts it from Renovate's weekly batching — `vulnerabilityAlerts` runs on
`schedule: ["at any time"]` with `prCreation: "immediate"`, alongside
`osvVulnerabilityAlerts`. A fix pull request therefore opens as soon as an
advisory lands, which is the same outcome enabling Dependabot's automated fixes
would buy. Running both puts two bots on one job: competing pull requests
against the same manifest, in repositories that are rebase-merge-only, so the
second one read is a conflict to resolve rather than a duplicate to close.

One dependency is worth naming, because it inverts the obvious cleanup:
`vulnerabilityAlerts` is Renovate reading *GitHub's* Dependabot alerts — it
requires the dependency graph and Dependabot alerts switched on, and the app
granted read access to them. Switching the alerts off to "finish" retiring
Dependabot would therefore disable Renovate's main security path, leaving only
`osvVulnerabilityAlerts`, which covers direct dependencies alone. The alerts are
load-bearing; only the automated fixes are redundant.

Revisit if Renovate stops opening a fix pull request within a day of an alert
appearing, or if Renovate is dropped as the update tool. Automated security
fixes are a per-repository setting and reversible either way.

### Decision: CodeQL advanced setup, not default setup

Decided 2026-08-29, for `apps`. CodeQL runs from a checked-in
`.github/workflows/codeql.yml` instead of GitHub's default setup, and the
hourly `prune-actions-cache.yml` that default setup made necessary is deleted.

Default setup enables dependency caching unconditionally on GitHub-hosted
runners and writes each Java/Go dependency archive under a content-derived key
that never repeats. Measured on 2026-08-29: 25 `codeql-*` entries holding
3.88 GiB of a 5.83 GiB total cache, individual Java entries 252-303 MiB, three
per open pull request even with hourly pruning. The prune workflow ran 447
times in the preceding 28 days (112 runs/week, about 119 billed runner-minutes
per week at one billed minute per ten-second run) and its only job was cleaning
up after another tool. Nothing in the repository could touch the cache key.

Advanced setup exposes the same switch as the `dependency-caching` input, off
by default, so the write stops at its source. The workflow mirrors the
default-setup configuration it replaces — languages, `default` query suite,
`remote` threat model, weekly schedule — and keeps the `/language:<name>`
category, so alerts share one analysis origin across the switch. Per-push
runner cost is unchanged: the same four extractors run once each.

Code quality is out of scope here and unchanged: it still runs on default
setup as its own dynamic workflow, because `codeql-action` rejects the
`analysis-kinds` input in checked-in workflows, and whether it stays on is a
separate decision. It also runs a Java extractor, so if `codeql-dependencies-*`
cache entries keep appearing after the switch, it is the remaining writer to
look at.

Alert continuity was the stated reason not to do this by default. Measured
before the switch, it cost nothing: zero open CodeQL alerts (the two open
alerts were both Trivy), and the two closed CodeQL alerts stay in the closed
list — a setup change does not delete history.

What this trades away: GitHub no longer updates the configuration for us. The
`codeql-action` pin is owned by Renovate like every other action in the org;
a new language or a query-suite change is a pull request rather than a
settings toggle. Revisit if default setup gains a way to disable dependency
caching, at which point the workflow could go back to being GitHub-managed —
though the reason to would be weak, since the checked-in file is also the
only reviewable record of what is scanned.

The other repositories are unaffected: CodeQL is still `apps`-only, and step 3
of the rollout plan below should use this workflow shape rather than default
setup so the same cache problem is not re-created there.

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
dependency updates, secret scanning + push protection. Extending CodeQL from
`apps` to `platform`/`infrastructure`/`deployments` is a repo-by-repo addition
(follow-up ticket — Go/shell-heavy repos get less value from CodeQL than `apps`
does, so sequence `apps`-like repos first). Since this evaluation, dependency
updates consolidated onto Renovate rather than Dependabot, which changes who
opens the pull requests but not the layering argument.

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
- **tfsec / Checkov / KICS / kube-linter / Kubescape / hadolint /
  OSV-Scanner individually** — all subsumed by Trivy's fs-mode scanners for
  this stack. Not worth the added workflow surface unless Trivy's coverage
  proves insufficient for a specific artifact type.
- **gitleaks** — judged subsumed by Trivy's secret scanner at evaluation time.
  **This call was later reversed.** Trivy's findings are advisory by default,
  and a leaked secret is the one class of finding that has to block a merge
  rather than land in a dashboard. gitleaks was adopted as a separate blocking
  job with an org-wide config and a value-pinned allowlist — something the
  Trivy job's single `fail-on-findings` switch could not express without also
  gating every vulnerability and misconfiguration finding. It is the one
  deferral in this document that did not hold.
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

The evaluation shipped as `security-scan.yml`, a reusable `workflow_call`
workflow running Trivy in fs mode and uploading SARIF via
`github/codeql-action/upload-sarif`, wired into `apps` alone and gating nothing.
It has gained jobs and callers since. For what it runs now, see
[`.github/workflows/README.md`](../.github/workflows/README.md) — that file is
authoritative and this paragraph describes only the starting point.

## Rollout plan

Steps 1 and 2 are complete; steps 3-5 remain open. The current set of callers
is listed in the owner doc, not here.

1. ~~Reusable workflow + PoC wired into `apps` (non-blocking).~~ Done.
2. ~~Wire the same reusable workflow into `platform`, `infrastructure`,
   `deployments`.~~ Done — as one shared caller rather than the per-repo
   variants anticipated here. The per-repo scan-path concern that motivated
   splitting it up (`infrastructure`'s Talos machine-config templates are not
   plain YAML and need rendering before static analysis) has not yet required
   a per-repo `scan-path`.
3. Extend CodeQL to the other 3 repos (separate follow-up, GitHub-native,
   no new tooling). Still outstanding — CodeQL remains `apps`-only.
4. After a burn-in period with Trivy advisory across all repos (confirm the
   finding volume is real signal, not noise), consider gating on
   CRITICAL/HIGH and adding the Trivy job as a required status check in each
   repo's ruleset. Note that the blocking gates added since this plan was
   written block via the job itself, not via a required status check, so they
   do not settle this question.
5. Semgrep OSS evaluation as a follow-up only if a concrete Go/Kotlin SAST
   gap is identified after Trivy + CodeQL are both running for a while.

## Evaluated on paper only (not run)

SonarQube CE/Cloud, Semgrep OSS, tfsec, Checkov, KICS, kube-linter,
Kubescape, hadolint, OSV-Scanner — ruled out or deferred per the
recommendation above without a hands-on run, since Trivy's fs-mode scanners
cover the same ground for this stack. If any of these get revisited, verify
against the actual repo content before adopting (this doc's judgment calls
are based on published tool docs + this org's stack, not a live trial of
each).

gitleaks was on this list and is no longer: it was adopted and is running. See
the reversal note under "Not recommended (for now)". That it moved from
paper-only to a blocking gate without this list being updated is why the
workflow's behaviour is documented in one place now, and not here.
