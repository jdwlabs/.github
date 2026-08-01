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

## Tag Convention

| Repo type | Tag format | Example |
|---|---|---|
| Single-artifact | `v{MAJOR}.{MINOR}.{PATCH}` | `v1.5.2` |
| Monorepo component | `{component}-v{MAJOR}.{MINOR}.{PATCH}` | `usersui-v1.3.6` |

All tags include the `v` prefix on the version segment. See org-level rulesets for tag protection rules.
