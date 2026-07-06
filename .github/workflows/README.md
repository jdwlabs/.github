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

Callers must set the appropriate `permissions` and trigger (always `push: tags`). The reusable workflow inherits the calling repo's `GITHUB_TOKEN` automatically.

---

## `release-go.yml` — Go Binary Release

Runs GoReleaser to cross-compile and publish a Go binary release.

**Trigger:** `push: tags: ['v[0-9]*']`

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `goreleaser-config` | No | `.goreleaser.yaml` | Path to GoReleaser config |
| `go-version-file` | No | `go.mod` | Path to `go.mod` or `go.work` for version resolution |

**Example caller:**

```yaml
# .github/workflows/release.yml
name: Release

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
      goreleaser-config: .goreleaser.yaml
```

**Used by:** `infrastructure` (talops), `platform` (platformctl)

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

## `security-scan.yml` — Security Scan (Trivy + SARIF)

Runs Trivy in filesystem mode (SCA + IaC/Dockerfile misconfig + secrets) and
uploads results as SARIF to the calling repo's Security tab. See
`docs/code-scanning-strategy.md` for the tooling evaluation behind this
choice.

**Trigger:** any (typically `pull_request` + `push: main`)

**Inputs:**

| Input | Required | Default | Description |
|---|---|---|---|
| `scan-path` | No | `.` | Repo-relative path to scan |
| `severity` | No | `CRITICAL,HIGH` | Comma-separated severities Trivy reports |
| `fail-on-findings` | No | `false` | Fail the job on findings at/above `severity`. SARIF uploads regardless. |

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

**Used by:** `apps` (PoC, JDWLABS-71)

---

## Tag Convention

| Repo type | Tag format | Example |
|---|---|---|
| Single-artifact | `v{MAJOR}.{MINOR}.{PATCH}` | `v1.5.2` |
| Monorepo component | `{component}-v{MAJOR}.{MINOR}.{PATCH}` | `usersui-v1.3.6` |

All tags include the `v` prefix on the version segment. See org-level rulesets for tag protection rules.
