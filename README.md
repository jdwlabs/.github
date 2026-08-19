# .github

[![License](https://img.shields.io/badge/License-PolyForm%20NonCommercial%201.0-blue)](https://polyformproject.org/licenses/noncommercial/1.0.0/)

The org-wide meta repository for [jdwlabs](https://github.com/jdwlabs): community health files GitHub applies as fallbacks to any repo that doesn't define its own, the reusable workflows the delivery repos call by `@main`, and the shared configuration those workflows and bots read from here.

Changes here reach every other repository. The reusable workflows and `gitleaks.toml` are consumed at `@main`, so a merge takes effect immediately for all callers with no version bump anywhere.

Internal-only counterpart: [`jdwlabs/.github-private`](https://github.com/jdwlabs/.github-private) — org profile content and infrastructure docs that shouldn't be public. GitHub only reads community health files and the profile README from *this* repo, so `.github-private` is never applied as an org-wide fallback.

## Community health files

| File | Purpose |
|------|---------|
| [`profile/README.md`](profile/README.md) | Public org profile shown on the jdwlabs GitHub page |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contribution guidelines — commit conventions, branch naming, PR process |
| [`SECURITY.md`](SECURITY.md) | Vulnerability disclosure policy |
| [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) | Code of conduct for all org spaces |
| [`PULL_REQUEST_TEMPLATE.md`](PULL_REQUEST_TEMPLATE.md) | Default PR template pre-filled on all new PRs |
| [`ISSUE_TEMPLATE/bug_report.md`](ISSUE_TEMPLATE/bug_report.md) | Bug report issue template |
| [`ISSUE_TEMPLATE/feature_request.md`](ISSUE_TEMPLATE/feature_request.md) | Feature request issue template |
| [`ISSUE_TEMPLATE/config.yml`](ISSUE_TEMPLATE/config.yml) | Disables blank issues, links security advisory |

## Workflows

Full inputs, callers and behaviour: [`.github/workflows/README.md`](.github/workflows/README.md).

| Workflow | Kind | Purpose |
|---|---|---|
| [`release-go.yml`](.github/workflows/release-go.yml) | Reusable | GoReleaser cross-compile and release on tag push |
| [`release-helm.yml`](.github/workflows/release-helm.yml) | Reusable | Package a Helm chart, release it, update the gh-pages index |
| [`release-container.yml`](.github/workflows/release-container.yml) | Reusable | Multi-arch image build, registry push, changelog release |
| [`security-scan.yml`](.github/workflows/security-scan.yml) | Reusable | Trivy SARIF (advisory), gitleaks secrets gate and added-binary size gate (both blocking) |
| [`verify-pr-signatures.yml`](.github/workflows/verify-pr-signatures.yml) | Reusable | Fails a pull request carrying any commit GitHub does not report as `verified` |
| [`main-attribution.yml`](.github/workflows/main-attribution.yml) | Scheduled, local | Daily report of default-branch commits no merged pull request accounts for |
| [`dependabot-alert-report.yml`](.github/workflows/dependabot-alert-report.yml) | Scheduled, local | Weekly org-wide open Dependabot alert count, diffed against the previous run |
| [`ruleset-reconcile.yml`](.github/workflows/ruleset-reconcile.yml) | Scheduled, local | Daily report of Baseline rulesets diverging from the org contract; reports only, never applies |

`security-scan-self.yml` and `verify-pr-signatures-self.yml` apply the two gates to this repo by local path, so a pull request changing a gate is checked by its own version rather than by the copy on `main`.

The three scheduled workflows run here and only here — they read other repositories rather than being called by them, and none has a `pull_request` trigger, so none can become a check that blocks a merge.

## Org configuration

| Path | Purpose |
|---|---|
| [`.github/rulesets/`](.github/rulesets) | Branch rulesets for this repo managed as code — edit the JSON, merge, then run [`apply.sh`](.github/rulesets/apply.sh). Read [`docs/rulesets.md`](docs/rulesets.md) before renaming a required check |
| [`.github/rulesets/org-policy.json`](.github/rulesets/org-policy.json) | The contract every repo's Baseline ruleset must satisfy, and the declared exceptions to it |
| [`.github/CODEOWNERS`](.github/CODEOWNERS) | Review routing; the reusable workflows and `gitleaks.toml` require owner review because every repo consumes them |
| [`default.json`](default.json) | Org-wide Renovate preset, extended by the other repos as `github>jdwlabs/.github` |
| [`renovate.json`](renovate.json) | This repo's own Renovate config — action pins for the reusable workflows |
| [`gitleaks.toml`](gitleaks.toml) | Org-wide gitleaks config and allowlist read by every caller of `security-scan.yml` |

`main` requires the four checks that report unconditionally on every pull request — `scan / scan`, `scan / gitleaks`, `scan / binaries` and `signatures / signatures`. The code-scanning check Trivy's SARIF upload produces is deliberately not required: it is published by the code-scanning app rather than by the workflow, so it can fail to appear at all, and a required check that never appears blocks the branch permanently.

## Docs

| Doc | Subject |
|---|---|
| [`docs/code-standards.md`](docs/code-standards.md) | Org-wide code quality contract, the gates that enforce it, and when to re-run them |
| [`docs/code-scanning-strategy.md`](docs/code-scanning-strategy.md) | Tooling evaluation behind the security scan, and why Dependabot fixes stay off |
| [`docs/rulesets.md`](docs/rulesets.md) | Where rulesets live, the org-wide contract, applying them, and the sequence for renaming a required check |
| [`docs/branch-protection-bypass.md`](docs/branch-protection-bypass.md) | Why each ruleset bypass exists and what would remove it |
| [`docs/agentic-operating-model.md`](docs/agentic-operating-model.md) | Identity, review, scaling and safety model for agent-authored change |
| [`docs/repo-health-visibility.md`](docs/repo-health-visibility.md) | Cross-repo audit and the decision against building a developer portal or dashboard |
