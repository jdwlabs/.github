# jdwlabs Reusable Workflows

Org-wide reusable workflows callable by any jdwlabs repository via `uses:`.

## Usage

Reference a workflow from any repo:

```yaml
jobs:
  release:
    uses: jdwlabs/.github/.github/workflows/release-helm.yml@main
    with:
      charts-dir: helm-charts
      pages-url: https://jdwlabs.github.io/platform
```

Callers must set the appropriate `permissions` and trigger — `push: tags` for the release workflows, `pull_request` for the gates. The reusable workflow inherits the calling repo's `GITHUB_TOKEN` automatically.

---

## `release-go.yml` — Go Binary Release

Runs GoReleaser to cross-compile and publish a Go binary release.

**Trigger:** `push: tags: ['v[0-9]*']`

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `goreleaser-config` | No | `.goreleaser.yaml` | Path to GoReleaser config (resolved relative to `workdir`) |
| `go-version-file` | No | `go.mod` | Path to `go.mod` or `go.work` for version resolution (repo-relative) |
| `workdir` | No | `.` | Working directory containing the Go module, for monorepo subdirectories |

**Example caller (module in a subdirectory):**

```yaml
# .github/workflows/release-platformctl.yml
name: Release platformctl

on:
  push:
    tags:
      - 'v[0-9]*'

permissions:
  contents: write

jobs:
  release:
    uses: jdwlabs/.github/.github/workflows/release-go.yml@main
    with:
      workdir: cli
      go-version-file: cli/go.mod
```

**Used by:** `platform` (platformctl). `infrastructure` (talops) intentionally keeps a bespoke release job: its artifacts are raw `talops-<os>-<arch>` binaries (not GoReleaser archives), it injects the `v`-prefixed tag into `cmd.version`, and it runs `go test -race` as a release gate — swapping blind would change published artifact names and drop the test gate.

---

## `release-helm.yml` — Helm Chart Release

Packages a Helm chart on tag push, creates a GitHub release with the `.tgz` attached, and updates the gh-pages Helm repo index.

**Trigger:** `push: tags: ['*-v[0-9]*']` (e.g. `tenant-envelope-v1.0.1`)

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `charts-dir` | Yes | — | Directory containing chart subdirectories (`helm-charts` or `charts`) |
| `pages-url` | Yes | — | GitHub Pages base URL for Helm index (e.g. `https://jdwlabs.github.io/platform`) |

**Tag format:** `{chart-name}-v{MAJOR}.{MINOR}.{PATCH}` — the workflow parses the component name and version from the tag automatically.

**Example caller:**

```yaml
# .github/workflows/release-charts.yml
name: Release Chart

on:
  push:
    tags:
      - '*-v[0-9]*'

permissions:
  contents: write
  pages: write

jobs:
  release:
    uses: jdwlabs/.github/.github/workflows/release-helm.yml@main
    with:
      charts-dir: helm-charts
      pages-url: https://jdwlabs.github.io/platform
```

**Used by:** `platform` (Helm charts), `deployments` (deployment charts)

---

## `release-container.yml` — Container Image Release

Builds a multi-arch container image, pushes to a registry, and creates a GitHub release with auto-generated changelog.

**Trigger:** `push: tags: ['*-v[0-9]*', '*-[0-9]*']` (new and legacy formats during Nx migration)

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `component` | Yes | — | Component name matching the image name and Nx project |
| `registry` | No | `ghcr.io` | Container registry hostname |
| `image-repo` | Yes | — | Image repository path under the registry (e.g. `jdwlabs`) |
| `dockerfile` | No | `Dockerfile` | Path to the Dockerfile |
| `context` | No | `.` | Docker build context |
| `platforms` | No | `linux/amd64,linux/arm64` | Target platforms |

**Tag format:** `{component}-v{MAJOR}.{MINOR}.{PATCH}` (new) or `{component}-{MAJOR}.{MINOR}.{PATCH}` (legacy `@jscutlery/semver` — remove after Nx release migration).

**Example caller:**

```yaml
# .github/workflows/release-usersui.yml
name: Release usersui

on:
  push:
    tags:
      - 'usersui-v[0-9]*'

permissions:
  contents: write
  packages: write

jobs:
  release:
    uses: jdwlabs/.github/.github/workflows/release-container.yml@main
    with:
      component: usersui
      image-repo: jdwlabs
```

**Used by:** `apps` (post Nx release migration)

---

## `security-scan.yml` — Security Scan (Trivy + SARIF, gitleaks and binary gates)

Three jobs:

- **`scan`** — Trivy in filesystem mode (SCA + IaC/Dockerfile misconfig +
  secrets), uploading results as SARIF to the calling repo's Security tab.
  Advisory by default (`fail-on-findings`). See
  `docs/code-scanning-strategy.md` for the tooling evaluation behind this
  choice.
- **`gitleaks`** — blocking secrets gate. Runs gitleaks (pinned, checksum
  verified) over the checked-out tree with the org-wide config
  (`gitleaks.toml` at this repo's root, fetched at `config-ref`, default
  `main`). Any leak fails the job; zero findings passes with an explicit
  message. Allowlist entries are value-pinned to known-fake fixtures — add new
  exemptions there, never in caller repos.
- **`binaries`** — blocking size gate on binary files a pull request *adds*.
  Runs on `pull_request` events only (it needs a base to diff against) and
  skips otherwise. Walks every commit in `base..head` rather than the net
  diff, because these repos rebase-merge: a branch that adds a blob and
  deletes it in a later commit still lands the blob on `main` permanently.
  Binary-ness is git's own content test (`--numstat` reporting `-`/`-`), not
  an extension list. Scoped to added files (`--diff-filter=A`), so existing
  repo content is never rewritten to adopt the gate. Any added binary larger
  than `max-binary-bytes` fails the job with the offending path, size, and
  commit. Raise `max-binary-bytes` in the caller when a large asset genuinely
  belongs in git.

**Trigger:** any (typically `pull_request` + `push: main`); the `binaries` job runs only on `pull_request`

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `scan-path` | No | `.` | Repo-relative path to scan (Trivy job) |
| `severity` | No | `CRITICAL,HIGH` | Comma-separated severities Trivy reports |
| `fail-on-findings` | No | `false` | Fail the Trivy job on findings at/above `severity`. SARIF uploads regardless. |
| `config-ref` | No | `main` | jdwlabs/.github ref to fetch `gitleaks.toml` from. A reusable workflow cannot resolve its own ref, so this cannot be inferred: if you pin the workflow to a non-main ref (e.g. pre-merge testing), pass that same ref here or the pinned logic runs against `main`'s config. |
| `max-binary-bytes` | No | `1048576` (1 MiB) | Largest binary file a pull request may add (`binaries` job). Raise deliberately in the caller when an asset genuinely belongs in git. |

**Example caller:**

```yaml
# .github/workflows/security-scan.yml
name: Security Scan

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  security-events: write

jobs:
  scan:
    uses: jdwlabs/.github/.github/workflows/security-scan.yml@main
```

**Used by:** `apps`, `platform`, `infrastructure`, `deployments`, and this repo
via `security-scan-self.yml`.

This repo's own caller differs from the four above in two ways, both deliberate:

- It references the workflow by **local path** (`./.github/workflows/security-scan.yml`)
  rather than `@main`, so a pull request changing the reusable workflow is gated
  by the version in that pull request instead of the copy already on `main`.
- It passes `config-ref: ${{ github.head_ref || github.ref_name }}`, because
  `gitleaks.toml` lives here — a pull request editing the allowlist must be
  scanned with the edited config, not with `main`'s.

Callers in other repos want neither behaviour: they should track the reviewed
workflow on `main`, and they do not own the config.

### What each job actually contributes here

The three jobs are called as a unit and cannot be selected individually, so this
is a record of what the scan is really worth on a repository of Markdown,
workflow YAML and org config — not a claim that all three pull equal weight.

| Job | Contribution to this repo |
| --- | --- |
| `gitleaks` | The one that earns it. Templates, workflow YAML and JSON config are exactly the file types a pasted token lands in, and this gate blocks. |
| `binaries` | Cheap and repo-agnostic. The incident behind it — a build artifact reaching `main` and staying in history under rebase-merge — does not care what a repo contains. |
| `scan` (Trivy) | Close to inert here, and worth stating plainly. There are no lockfiles, so `vuln` has nothing to resolve; `misconfig` targets Dockerfiles, Kubernetes, Terraform, CloudFormation, ARM and Helm, none of which exist in this repo. Only its `secret` scanner sees anything, and that overlaps `gitleaks`, which already blocks. It costs one advisory job and is left enabled for uniformity with the other four callers. |

Trivy's misconfiguration scanner does **not** cover GitHub Actions workflow
files, which is most of this repo's non-Markdown content. Anyone reasoning about
coverage here should not assume the workflow YAML is being statically analysed —
`actionlint` is what reads it, and that runs locally rather than in this
pipeline.

---

## `verify-pr-signatures.yml` — Pull Request Commit Signatures

Reads every commit in a pull request through the API and fails if any is not
`verified`. Each offending commit is named with its short SHA, subject, author
and GitHub's own `reason` (`unsigned`, `bad_email`, `unknown_key`, …), so a red
check says which commit and why. A clean branch reports `N commit(s), all
verified — passed` rather than passing silently.

**Why the branch and not `main`.** A signature only survives as far as the
merge. GitHub rebuilds every commit server-side when it rebase-merges and signs
none of the results — including on a branch already rebased onto the base, where
there is nothing to replay. A signature requirement on a rebase-merged base
branch is therefore unsatisfiable by construction, which is why merges here need
`--admin`. Enforcing on the branch gates the artefact whose signature is real:
the author's. What lands on the base branch afterwards is GitHub's own object,
so gating its signature would only ever assert something about GitHub.

**Trigger:** `pull_request`. The job skips on any other event — there is no
branch to attest.

**Inputs:** none.

**Permissions:** `contents: read`, no secret. All five repos are public and the
job never checks out code; it reads the API with `GITHUB_TOKEN`.

**No local `git verify-commit`.** The runner holds no keyring and no basis for
trusting one. GitHub's `verified` field checks the signature against the keys
registered to the authoring account, which is the property worth gating on.

**No author allowlist.** Commits an App creates through the API (Renovate,
Dependabot, the release bot) are signed with GitHub's own web-flow key and
verify natively, so they need no exemption. An allowlist keyed on author name
would be a hole that any commit claiming that name walks through. An App commit
that a later rebase rewrites does lose its signature, and correctly fails.

**Behaviours worth knowing before you hit them:**

| Case | Result |
| --- | --- |
| Fork pull request | Works. The base repo's PR-commits endpoint returns the fork's commits, and the read-only `GITHUB_TOKEN` a fork PR receives still carries `contents: read` on a public repo. A fork contributor must have their signing key registered on *their* GitHub account and commit from a verified address — GitHub verifies against the author's account, not the org's. |
| Pull request with zero commits | Fails, deliberately. A branch reset to its base has nothing to attest, and reporting a pass over nothing is a green check backed by no evidence. Such a pull request has no changes to merge either. |
| Pull request over 250 commits | Fails. The commits endpoint caps at 250 and does not say when it truncates, so the job compares what it read against the event payload's count and refuses to pass over a partial branch. |
| API read error | Fails. A transient error would otherwise yield an empty commit list and a green check over a branch nothing inspected. |

**Example caller:**

```yaml
# .github/workflows/verify-pr-signatures.yml
name: Verify PR Signatures

on:
  pull_request:

permissions:
  contents: read

jobs:
  signatures:
    uses: jdwlabs/.github/.github/workflows/verify-pr-signatures.yml@main
```

**Used by:** `apps`, `platform`, `infrastructure`, `deployments`, and this repo
via `verify-pr-signatures-self.yml`, which references the workflow by local path
for the same reason `security-scan-self.yml` does — a pull request changing the
check is gated by its own version, not by the copy already on `main`.

---

## `main-attribution.yml` — Default Branch Attribution

**Not reusable.** This one runs here and only here: it reads other repositories
rather than being called by them, so there is nothing for a caller to invoke.
It is documented alongside the reusable workflows because this file is where
anyone looks for what this repo's `workflows/` directory does.

**Trigger:** `schedule` daily at 13:17 UTC, plus `workflow_dispatch` with an
optional `days` input.

Reports any commit on a default branch that no *merged* pull request accounts
for. This is the detection half of branch protection: the `OrganizationAdmin`
bypass is deliberate and load-bearing, so the rule cannot be enforced at push
time for that actor — see [`docs/branch-protection-bypass.md`](../../docs/branch-protection-bypass.md)
for why it exists and what would remove it. This job makes an exercised bypass
visible instead of silent.

**Covers:** `deployments`, `platform`, `infrastructure`, and this repo.
**Not** `apps` — its release App still holds `bypass_mode: always` because
`nx release` must land the version commit before the release tags can point at
it, and no pull request fits inside that. Exempting it would mean an allowlist
keyed on committer name and subject line, both supplied by the commit itself.
Removing that bypass and adding `apps` here are the same change.

Attributability, not signedness. An earlier attempt gated the signature of each
default-branch tip and was abandoned: rebase merges are re-created server-side
and never signed, so once `required_signatures` came off `main` an unsigned tip
became the intended state and the job would have gone red daily over correct
behaviour. The pull request association is the property that survives a rebase
merge — GitHub keeps it — which is why this check gates on that instead.

| Situation | Behaviour |
|---|---|
| Commit with a merged pull request | Passes. |
| Commit with only an open or closed-unmerged pull request | Fails. That describes a proposal, not what landed. |
| Commit with no pull request at all | Fails, with the commit URL and its committer. |
| Over 100 commits in the window | Fails. 100 is the GraphQL page cap, so the job refuses to grade the portion that fitted; shorten `days` or page the query. |
| API read error | Fails. A transient error would otherwise yield an empty node list and a green tick over a branch nothing inspected. |
| Quiet repository, no commits in the window | Passes. Nothing landed, so there is nothing unattributed. |

The window is rolling rather than anchored to a policy date. Two classes of
unattributable commit sit in history and are not findings: the direct-push
chart bumps on `deployments` from before releases moved to pull requests, and
everything on `infrastructure` older than the GPG re-sign, which rewrote every
SHA and detached them all from their pull requests. A window ages both out. A
fixed cutoff would report them forever, and a check that is always red is a
check nobody reads. Any future history rewrite will surface here for as many
days as the window is long.

---

## `dependabot-alert-report.yml` — Weekly Dependabot Alert Report

**Not reusable.** Like `main-attribution.yml`, it reads other repositories
rather than being called by them.

**Trigger:** `schedule` weekly, Mondays at 13:00 UTC, plus `workflow_dispatch`.
There is no `pull_request` trigger, so it can never become a check that blocks a
merge.

**What it publishes.** One issue titled `Dependabot Alert Report`, edited in
place every run — reopened if it was closed, created with the `dependencies` and
`type:security` labels if it does not exist. The same report goes to the job
summary. It carries a severity/scope totals table, the same table broken down
per repo, and two lists: alerts new since the previous run and alerts resolved
since the previous run.

**Why it exists.** The alert backlog has been cleared twice and quietly
regenerated twice, both times noticed by accident on a `git push` banner. A flat
count read the same whether it was steady or refilled with new highs, so the
report diffs against the previous run rather than restating a total.

**Covers:** `apps`, `platform`, `infrastructure`, `deployments` and this repo.
`.github-private` has Dependabot alerts disabled at the repo level (confirmed
against the API, not assumed) and `demo-repository` is GitHub's own template
rather than a jdwlabs project — both are left out deliberately.

**Secret:** `DEPENDABOT_REPORT_TOKEN`, used only for the cross-repo alert read.
A workflow's default `GITHUB_TOKEN` is scoped to the repo it runs in and cannot
see alerts on any other, so the fan-out needs its own token. The issue
read/write stays on the default token.

**Permissions:** `contents: read`, `issues: write`, `actions: read` — the last
because the previous run's state is downloaded from that run's artifact.

**State lives in an artifact, not a commit.** The alert-identity list from the
last run rides the `dependabot-alert-state` artifact (90-day retention). A
committed state file would need a direct push to `main`, which this repo's own
rulesets reject, and a weekly bookkeeping commit does not earn a pull request.

| Case | Result |
| --- | --- |
| No prior successful run | Starts from empty state; every open alert reports as new, once. |
| Prior run exists but its artifact expired or predates artifact upload | Same — empty state and a logged reason, rather than failing the job. |
| Alert count unchanged since last run | Still reports. A steady total with a different set of alerts shows up as non-empty new/resolved lists. |

---

## `ruleset-reconcile.yml` — Ruleset Conformance Report

Daily scheduled report (`41 7 * * *`) plus `workflow_dispatch`. Runs
`tools/check-ruleset-conformance.py` and fails the job on a finding. **It never
applies a ruleset** — applying needs admin on the target repository and has an
unenforced window, so the cutover stays a deliberate human action.

**Why it exists.** Rulesets are managed as code in five independent
per-repository directories, which is correct — required status checks name the
CI jobs of the repository they protect, and the repositories require between 4
and 13 different contexts. What was missing was anything comparing them, so
divergence with nothing to diverge *from* read as five deliberate choices. It is
not: one repository requires no approving review and one requires branches to be
up to date, and only one of those has a recorded reason.

**Contract:** [`.github/rulesets/org-policy.json`](../rulesets/org-policy.json).
Contexts are checked as a superset — extra repository-specific checks are
conforming. A deliberate divergence is declared there with a mandatory reason and
the exact value it excuses, so it expires when that value moves.

**Covers:** `apps`, `platform`, `infrastructure`, `deployments` and this repo.

**Two tiers.**

| Tier | Question | Token |
| --- | --- | --- |
| committed | Does each checked-in `baseline.json` satisfy the contract? | default `GITHUB_TOKEN`; all five repos are public |
| live | Does each checked-in `baseline.json` match the ruleset in force? | `RULESET_READ_TOKEN` |

**Secret:** `RULESET_READ_TOKEN` — a classic PAT with `repo` scope from an
account holding admin on all five repositories. Not yet set, so the live tier is
skipped; the report prints `LIVE COMPARISON NOT RUN` and the job raises a
workflow annotation. A tier that did not run is never reported as one that
passed. Reading rulesets needs repository-admin rights, not `admin:org`.

**Permissions:** `contents: read`.

| Exit | Meaning |
| --- | --- |
| 0 | Every baseline satisfies the contract. |
| 1 | A divergence, a stale exception, or a committed/live mismatch. |
| 2 | No verdict reached — unreadable policy or an API failure. Reported separately so "the check failed" is never read as "the check found something". |

Full background, the apply procedure and the required-check rename sequence:
[`docs/rulesets.md`](../../docs/rulesets.md).

---

## Tag Convention

| Repo type | Tag format | Example |
|---|---|---|
| Single-artifact | `v{MAJOR}.{MINOR}.{PATCH}` | `v1.5.2` |
| Monorepo component | `{component}-v{MAJOR}.{MINOR}.{PATCH}` | `usersui-v1.3.6` |

All tags include the `v` prefix on the version segment. See org-level rulesets for tag protection rules.
