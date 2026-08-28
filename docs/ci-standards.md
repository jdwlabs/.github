# CI/CD Standards & Attribution

A full inventory of every GitHub Actions workflow in the org, what identity
each one runs as, and where the org's CI/CD practice sits against a named
industry baseline. This is the audit `docs/repo-health-visibility.md` deferred
— that document answers "should we build a dashboard" (no); this one answers
"what does the estate actually contain, and who is allowed to act in it."

Audited 2026-08-21 against `origin/main` in all five repositories, via
`gh run list` (last 5 runs per workflow) and a full read of every workflow
file. Re-verify before trusting a row that predates a later merge — this is a
snapshot, not a live view.

---

## 1. The estate

38 workflow files across 5 repositories: `apps` (6), `deployments` (9),
`infrastructure` (6), `platform` (8), `.github` (9, of which 4 are
`workflow_call`-only reusable workflows never run standalone here).

The delivery-repo count has grown since the audit that opened this line of
work first counted 26 — `agent-identity.yml` alone was added to all four
delivery repos on 2026-08-19, and `ruleset-reconcile.yml` is new to `.github`
this week. Treat 26 as a historical starting point, not a target to
reconcile back to.

### `apps`

| File | Trigger | Purpose | Cadence / last run | Modified |
|---|---|---|---|---|
| `agent-identity.yml` | `pull_request` | Fails a PR where the agent App identity appears without a `Co-Authored-By` trailer | Every PR; 2026-08-21 success | 08-19 |
| `ci.yml` | `push`(main), `pull_request`, `workflow_dispatch` | Format, lint, test, sharded e2e, and on main-push: Nx release, image build/push, chart bump dispatch | Continuous, many/day; 2026-08-21 success | 08-19 |
| `codeql.yml` | `push`(main), `pull_request`, `schedule` weekly (Mon 04:17), `workflow_dispatch` | Checked-in CodeQL advanced setup (actions, go, java-kotlin, javascript-typescript; code-scanning only; code-quality stays on default setup, a separate toggle). Replaced default setup and the hourly `prune-actions-cache.yml` on 2026-08-29: default setup's dependency cache was the bloat the prune existed for, and advanced setup leaves it off | Continuous; new 2026-08-29 | 08-29 |
| `deliver-backfill.yml` | `workflow_dispatch` only | Manual recovery: rebuild/republish images for tag/version pairs a prior release run failed to deliver | Emergency-only; 1 run ever, 2026-07-24 success | 08-17 |
| `security-scan.yml` | `pull_request`, `push`(main, docs-excluded) | Caller into the org's reusable Trivy + gitleaks + binary-size scan | Continuous; 2026-08-21 success | 08-14 |
| `verify-pr-signatures.yml` | `pull_request` | Caller into the org's reusable commit-signature gate | Every PR; 2026-08-21 success | 07-31 |

### `deployments`

| File | Trigger | Purpose | Cadence / last run | Modified |
|---|---|---|---|---|
| `agent-identity.yml` | `pull_request` | Same co-authorship tripwire as `apps` | Every PR; 2026-08-21 success | 08-19 |
| `ci.yml` | `push`(main), `pull_request`, `workflow_dispatch` | Chart lint, template render against every env values file, image-pin check, promotion-tooling tests, ArgoCD config validation | Continuous, many/day; 2026-08-21 success | 08-14 |
| `e2e.yml` | `workflow_dispatch` only | Playwright suite against staging on the self-hosted ARC runner | Dormant — runner is down; last real trigger 2026-07-20, failing | 08-14 |
| `prd-drift.yml` | `schedule` daily (`06:23`) | Non-blocking report of charts where prd's `appVersion` trails the release beyond a threshold | Daily; **red 5/5 recent runs** as of 08-21 | 08-19 |
| `promote-prd.yml` | `workflow_run`(E2E, dormant) + `workflow_dispatch` | Opens the digest-pinned PR that bumps a chart's `values-prd.yaml` — the only sanctioned path to a prd image-tag change | On-demand; last 2026-08-05, success | 08-14 |
| `release.yml` | `push` tags `*-v[0-9]*` | Publishes a chart release via the reusable Helm-release workflow | **Zero runs ever** — no tag has ever matched the pattern | 08-13 |
| `security-scan.yml` | `pull_request`, `push`(main, docs-excluded) | Reusable scan caller | Continuous; 2026-08-21 mostly success (1 expected `cancelled`) | 08-14 |
| `update-pages.yml` | `workflow_run`(Release Chart) | Regenerates the Helm index page on `gh-pages` after a chart release | **Zero runs ever** — dependent on `release.yml`, which has never fired | 08-13 |
| `verify-pr-signatures.yml` | `pull_request` | Reusable signature-gate caller | Every PR; 2026-08-21 success | 07-31 |

### `infrastructure`

| File | Trigger | Purpose | Cadence / last run | Modified |
|---|---|---|---|---|
| `agent-identity.yml` | `pull_request` | Same co-authorship tripwire | Every PR; 2026-08-21 success | 08-19 |
| `bootstrap.yml` | `push`/`pull_request`(main), `paths: bootstrap/**, terraform/terraform.tfvars.example` | Lint/vet/test/build the `bootstrap/` Go module; checksum-verified install of sops/age/talosctl; Talos machine-config validation | Bursty, path-gated; 2026-08-19 success | 08-19 |
| `release.yml` | `push` tags `v*` | Cross-platform `talops` binary release + checksums | ~Monthly Apr–May 2026, idle since; last 2026-05-25 success | 08-17 |
| `security-scan.yml` | `pull_request`, `push`(main, docs-excluded) | Reusable scan caller | Continuous; 2026-08-21 success | 08-17 |
| `terraform.yml` | `push`/`pull_request`(main), `paths: terraform/**` | `terraform fmt -check` / `init` / `validate` | Path-gated, moderate; 2026-08-19 success | 08-17 |
| `verify-pr-signatures.yml` | `pull_request` | Reusable signature-gate caller | Every PR; 2026-08-21 success | 07-31 |

**`bootstrap.yml`'s `paths:` filter excludes `.github/workflows/**`** — a change
to the workflow file itself, including its checksum-pinned tool installs,
does not trigger the workflow to test itself. Already surfaced and exercised
by hand once (a forced run with throwaway commits covering both the
cache-hit and cache-miss paths). `terraform.yml` has the identical shape at
lower stakes — its own logic is fmt/validate only, no checksum pinning to
silently break.

### `platform`

| File | Trigger | Purpose | Cadence / last run | Modified |
|---|---|---|---|---|
| `agent-identity.yml` | `pull_request` | Same co-authorship tripwire | Every PR; 2026-08-21 success | 08-19 |
| `audit-admin-bypass.yml` | `schedule` daily (`12:00`), `workflow_dispatch` | Cross-repo (4 delivery repos) audit for agent-authored merges that were both unapproved and left a required check unsatisfied | Daily; 2026-08-20 success | 08-19 |
| `release-platformctl.yml` | `push` tags `v[0-9]*` | Releases the `platformctl` Go CLI via the reusable Go-release workflow | Idle since 2026-05-25 (v0.2.2); tag-triggered by design | 07-12 |
| `release.yml` | `push` tags `*-v[0-9]*` | Publishes a chart release via the reusable Helm-release workflow | **Zero runs ever** — same trigger/tag mismatch as `deployments`' `release.yml` | 08-17 |
| `security-scan.yml` | `pull_request`, `push`(main, docs-excluded) | Reusable scan caller | Continuous; 2026-08-21 success | 08-14 |
| `update-pages.yml` | `workflow_run`(Release Chart) | Regenerates the Helm index page after a chart release | **Zero runs ever** — dependent on `release.yml` | 08-17 |
| `validate.yml` | `pull_request`/`push`(main) | The repo's main gate: YAML/tenant/manifest validation, Prometheus/Alertmanager rule tests, CRD freshness, image pinning, ADR numbering, Go build/test/lint, Helm lint. 13 jobs. | Continuous, many/day; 2026-08-21 success | 08-19 |
| `verify-pr-signatures.yml` | `pull_request` | Reusable signature-gate caller | Every PR; 2026-08-21 success | 07-31 |

`audit-admin-bypass.yml`, `release.yml` and `update-pages.yml` share a
different shape of blind spot from the `paths:` case above: none has a
`pull_request` trigger, so a bug landing in any of the three, or in the
Python tool `audit-admin-bypass.yml` calls, gets zero CI signal on the PR
that introduces it.

### `.github`

| File | Trigger | Purpose | Cadence / last run | Modified |
|---|---|---|---|---|
| `dependabot-alert-report.yml` | `schedule` weekly (Mon 13:00), `workflow_dispatch` | Cross-org open Dependabot alert count, diffed against the prior run, published to one pinned issue | Weekly; 2026-08-17 success | 08-08 |
| `main-attribution.yml` | `schedule` daily (13:17), `workflow_dispatch` | Reports default-branch commits with no merged pull request behind them, across `deployments`/`platform`/`infrastructure`/`.github` | Daily; **2026-08-20 failed** — `platform` exceeded the 100-commit GraphQL page cap in-window, refused to report a partial pass | 08-03 |
| `release-go.yml` | `workflow_call` | Reusable GoReleaser release | Not run standalone (expected). Caller: `platform/release-platformctl.yml` | 08-01 |
| `release-helm.yml` | `workflow_call` | Reusable Helm chart release + gh-pages index update | Not run standalone (expected). Callers: `platform/release.yml`, `deployments/release.yml` (both currently dead — see §3) | 08-01 |
| `ruleset-reconcile.yml` | `schedule` daily (07:41), `workflow_dispatch` | Compares every repo's committed ruleset against `org-policy.json`; reports and fails, never applies | Daily; new this week, first run **failed with a real divergence** (correct behaviour) | 08-19 |
| `security-scan-self.yml` | `pull_request`, `push`(main) | Self-test caller of `security-scan.yml` via **local path**, so an edit to the reusable workflow is gated by its own version | Continuous; 2026-08-21 success | 07-29 |
| `security-scan.yml` | `workflow_call` | Reusable Trivy + gitleaks + binary-size scan | Not run standalone (expected). Callers: all 4 delivery repos + this repo's self-test | 08-01 |
| `verify-pr-signatures-self.yml` | `pull_request` | Self-test caller of `verify-pr-signatures.yml` via local path | Every PR; 2026-08-21 success | 07-31 |
| `verify-pr-signatures.yml` | `workflow_call` | Reusable commit-signature gate | Not run standalone (expected). Callers: all 4 delivery repos + this repo's self-test | 07-31 |
| `tools-tests.yml` | `pull_request`, `push`(main) | Unit tests for `tools/` — the vendored `check-image-pins.py` and the scheduled ruleset checker, neither of which gets PR signal any other way | Every PR; new 2026-08-29 | 08-29 |

---

## 2. Identity & token attribution

**The default posture is the ephemeral, per-run `GITHUB_TOKEN`, narrowly
scoped by an explicit `permissions:` block.** That covers every workflow in
the inventory above except the five rows below, which mint or hold a
longer-lived credential because the default token cannot reach across
repositories.

| Identity | Secret(s) | Where it's minted | Scope | Why the default token can't do this |
|---|---|---|---|---|
| Release App (`jdwlabs-release-bot`) | `RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY` | `apps/ci.yml` (`release`, `dispatch-e2e` jobs); `apps/deliver-backfill.yml` (passed into app code, not minted in YAML) | Per-mint `repositories:` scoping — `apps` for the release job, `deployments` for the cross-repo e2e dispatch — even though the App is installed org-wide | A workflow's default token can only push to the repo it runs in; releasing needs write on `apps`, dispatching e2e needs write on `deployments` |
| Release App (same App, prd path) | `RELEASE_APP_ID` / `RELEASE_APP_PRIVATE_KEY` | `deployments/promote-prd.yml` | `repositories: deployments` | Opens the prd promotion PR. **Does not merge it** — GitHub refuses an App's self-approval, which is why this repo's required-approval count is 0 rather than a bot self-approve flow; merging that PR is a human action gated by 9 required checks, linear history, and code-owner review on prd paths. |
| Agent App | `AGENT_APP_ID` / `AGENT_APP_PRIVATE_KEY` | `platform/audit-admin-bypass.yml` | `repositories: apps,platform,infrastructure,deployments` — **the broadest-scoped token in the inventory** | The daily bypass audit reads merge/review/check state across all four delivery repos; nothing narrower reaches that far |
| Dependabot report token | `DEPENDABOT_REPORT_TOKEN` | `.github/dependabot-alert-report.yml` | Cross-org read of Dependabot alerts (plain secret, not an App installation token — no `create-github-app-token` step involved) | The Dependabot Alerts API for another repository is invisible to that repo's own default token |
| Ruleset read token | `RULESET_READ_TOKEN` | `.github/ruleset-reconcile.yml` | Documented as a classic PAT, `repo` scope, held by an account with admin on all five repos. **Not yet set** — the live-comparison tier is skipped and the report says so explicitly rather than reporting a false pass | Reading a *live* (as opposed to committed) ruleset needs repository-admin rights on each target repo |

**Bot commit identity is a third, distinct category from the two above and
is not yet consistent.** `update-pages.yml` in both `platform` and
`deployments` sets a `github-actions[bot]` git commit identity by local
`git config` before pushing to `gh-pages` — this is a commit-author label
under the ambient `GITHUB_TOKEN`, not a separate credential, and it is
unrelated to the Release App identity used in the same two repos'
`promote-prd.yml`/`ci.yml`. Extending a deliberate, consistent commit
identity to every bot-authored commit — beyond `apps`, where it was
corrected as part of this line of work — is tracked as open scope, not
resolved by this document.

**`agent-identity.yml`, present in all four delivery repos, is the mirror
case: it checks for an identity rather than minting one.** It runs entirely
on the default read-only token and fails a PR where the `jdwlabs-agent-bot`
App identity appears without the `Co-Authored-By: ... @anthropic.com`
trailer the org's authorship contract requires.

---

## 3. Legacy / low-value workflow verdicts

| Workflow | Verdict | Rationale |
|---|---|---|
| `deployments/release.yml`, `platform/release.yml` | **Keep, pending a tag-convention decision** | Zero runs ever — the trigger pattern (`*-v[0-9]*`) has never matched any tag actually cut (`{component}-{version}`, no `v`). Not a dead workflow to retire; it's a live workflow whose trigger doesn't match reality. Fixing the glob is a policy call (align the pattern to the tags in use, or start cutting tags with `v`) already raised separately — resolving it, not this document, decides the verdict. |
| `deployments/update-pages.yml`, `platform/update-pages.yml` | **Keep, no independent action** | Both are dead purely as a consequence of the `release.yml` rows above (`workflow_run` triggers on a workflow that never completes). Resolve automatically once those are fixed; nothing to do here independently. |
| `apps/deliver-backfill.yml` | **Keep** | `workflow_dispatch`-only by design, one historical run. It exists for exactly the failure mode it names — `ci.yml`'s release job tags successfully but a later step in the same run fails — and a near-zero run count is what a working emergency tool looks like, not evidence of neglect. |
| `deployments/e2e.yml` | **Keep, currently dormant** | Manual-only because the self-hosted ARC runner it needs is down; the file's own header documents the `repository_dispatch` trigger that existed before and names it as the thing to restore once the runner is back. The recent run history (all `failure`, all `repository_dispatch`) predates the trigger's removal and is stale evidence, not current signal. |
| `infrastructure/release.yml`, `platform/release-platformctl.yml` | **Keep** | Idle several weeks to a few months, but both are tag-triggered binary releases — idle is the expected state between releases, not a sign of drift. |
| `.github/release-container.yml` | **Retired (deleted)** | Reusable, `workflow_call`-only, and the direct check found no consumer: zero hits from GitHub code search across the org and from a clone-and-grep of every org repository (`apps`, `deployments`, `infrastructure`, `platform`, `.github-private`, `demo-repository`). The README's claimed consumer (`apps`, after the Nx release migration) never materialised — `apps/ci.yml` already runs `nx release` and builds and pushes images through each project's `build-image` target, so nothing plans to adopt it. |
| `deployments/prd-drift.yml` | **Keep, needs a human look** | Doing its job by design (report, never promote) — but 5/5 recent daily runs are red, which is exactly the ambiguity `docs/repo-health-visibility.md` §3 already named: a job red by design and a job red because it broke look identical from outside. Worth confirming prd is actually behind rather than assuming the red is expected. |
| `.github/main-attribution.yml` | **Keep** | The 2026-08-20 failure is the workflow refusing to report a partial pass when `platform` exceeded its 100-commit page cap in one window — correct behaviour under load, not a defect. Worth knowing a busy week can trip this, not worth changing. |
| Everything else in the inventory (24 of 38 files) | **Keep, no verdict needed** | Fires on every PR or push, green on its last run, and gates or reports something with a live consumer. |

---

## 4. Baseline: OpenSSF Scorecard

`docs/repo-health-visibility.md` §4 already ran OpenSSF Scorecard
(`gcr.io/openssf/scorecard:stable`, v5.1.1-45-g40bbc9c9) against every
repository's live default branch on 2026-08-18, reproduced 2026-08-20. That
table is the org's named industry baseline and is not repeated here — see
that document for the full per-check breakdown and the reading notes on
which zeros are structural (`Code-Review`, an artifact of a one-human org)
versus real and actionable (`Pinned-Dependencies`, genuinely zero: no
action, no reusable-workflow reference, and no `pip install` anywhere in
this inventory is pinned by hash).

Two things this document adds on top of that baseline, both visible only
from the full workflow inventory rather than from Scorecard's per-repo
scan:

- **The floating-reference finding is org-wide, not per-repo — resolved
  2026-08-28.** Every delivery repo called this repo's reusable workflows
  at `@main` (`security-scan.yml` and `verify-pr-signatures.yml` in all
  four; `release-helm.yml` and `update-pages.yml` in `platform` and
  `deployments`; `release-go.yml` in `platform` — 13 caller lines total).
  A merge here changed behaviour for every caller immediately, with
  no version bump anywhere — the least-trusted boundary in the dependency
  graph was also the least pinned one.

  **Decision: pin to a full commit SHA, not a tag.** This repo has no
  tagged releases (`git tag` is empty, no GitHub Releases), so a tag-pin
  scheme would mean inventing a release process for a repo that has never
  needed one just to have something to point at — a SHA pin needs nothing
  new. Every caller line now reads
  `uses: jdwlabs/.github/.github/workflows/<file>.yml@<full-sha>  # main as of YYYY-MM-DD (jdwlabs/.github has no tagged releases)`,
  the comment recording the date the SHA was `main`'s tip, for a human
  reading the pin without resolving it. If this repo ever starts tagging
  releases, the comment convention becomes `# vX.Y.Z` and existing pins
  should migrate opportunistically, not in a forced sweep.

  **Update mechanism: Renovate, already wired.** `default.json`'s
  `github-actions` manager (via `config:recommended`) tracks a full-SHA
  `uses:` pin as a digest dependency and opens a PR when `main` moves;
  `digest` is already in the `matchUpdateTypes` batched into the weekly
  "all non-major dependencies" group in every delivery repo's Renovate
  config (each `extends: ["github>jdwlabs/.github"]`). No new Renovate
  config was needed — digest updates for these pins ride the same weekly
  batch as every other pinned Action.

  **Trade-off accepted.** A behaviour change to a reusable workflow no
  longer reaches every caller the moment it merges to `main` here; it reaches
  each caller only after that caller's next Renovate digest-bump PR is
  reviewed and merged. For a single-maintainer org this trades instant
  propagation for a review point on every behaviour change to the
  least-trusted boundary in the dependency graph — the trade this document
  already named as worth making. This repo's own two self-test callers
  (`security-scan-self.yml`, `verify-pr-signatures-self.yml`) keep the
  strictest available pin — local path, same commit — unaffected by this
  change.
- **Two GitHub-owned actions break house pinning convention.**
  `actions/upload-artifact@v7` (`.github/dependabot-alert-report.yml`) and
  `github/codeql-action/upload-sarif@v4` (`.github/security-scan.yml`) are
  pinned to a major version only, unlike every other action reference in
  scope, which carries a full `vMAJOR.MINOR.PATCH`.

## 5. Shared scripts vendored into delivery repos

Some CI gates are Python scripts rather than reusable workflows, and a
script cannot be `uses:`-referenced — it has to exist in the calling repo's
checkout. The rule for those is the same as for reusable workflows, applied
by hand:

- **The canonical copy lives here, under `tools/`**, with its tests under
  `tools/tests/` and `tools-tests.yml` gating every change to it.
- **Each consuming repo vendors the script and its test file byte-for-byte**
  and declares everything repo-specific (which paths are scanned, where the
  allowlist lives) in a config file next to it — never by editing the script.
- **The consuming repo's CI compares its copy against this repo at a pinned
  commit SHA** (`raw.githubusercontent.com/jdwlabs/.github/<sha>/tools/…`,
  with the same dated `# main as of <date>` comment) and fails on any
  difference. A rule fix therefore lands here first, then each consumer
  re-vendors and bumps its SHA in one PR; a consumer that skips that PR
  keeps running the older rules, but its own CI says so on every run
  rather than letting the two copies drift apart silently.

| Script | Consumers | What the per-repo config declares |
|---|---|---|
| `tools/check-image-pins.py` | `deployments`, `platform` | `tools/image-pin-check.yaml`: scan sources (`helm-overlays` for a `charts/<chart>/values-<env>.yaml` layout, `tree` globs for everything else) and the allowlist path |

## 6. Review cadence

This document is a snapshot, not a subscription — nothing re-runs it
automatically. The commitment: **re-run this audit (workflow inventory,
identity table, legacy verdicts) once per calendar quarter, or immediately
when a sixth repository joins the org, whichever comes first**, and fold the
result back into this file via pull request rather than a second, competing
copy. Between full audits, the pieces that change fastest are already
watched continuously by the workflows this document catalogs, not by a
human re-reading it:

- **Ruleset drift** — `ruleset-reconcile.yml`, daily.
- **Unattributed default-branch commits** — `main-attribution.yml`, daily.
- **Unapproved, unsatisfied agent-authored merges** — `audit-admin-bypass.yml`,
  daily.
- **Dependabot alert backlog** — `dependabot-alert-report.yml`, weekly.

A quarterly full re-audit is the right grain for this org's size: four of
the five findings in `docs/repo-health-visibility.md` §5 were counting or
config-drift problems invisible to any single repo's own CI, caught only by
looking across all of them at once — exactly what this document and its
successors are for. Revisit the cadence itself under the same trigger
`docs/repo-health-visibility.md` §9 already names for reconsidering a
heavier tooling build: a second human maintainer with write access joining
the org.
