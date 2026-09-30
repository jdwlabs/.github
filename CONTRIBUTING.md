# Contributing to jdwlabs

## Commit Messages

This org uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

| Type | When to use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `chore` | Maintenance, deps, tooling |
| `docs` | Documentation only |
| `refactor` | Code change with no feature or fix |
| `test` | Adding or updating tests |
| `ci` | CI/CD pipeline changes |
| `perf` | Performance improvement |

**Examples:**
```
feat(auth): add JWT refresh token support
fix(users-api): handle null email on registration
chore(deps): bump angular to 19.2
```

## Branch Naming

```
<type>/<short-description>
```

**Examples:**
```
feat/user-profile-page
fix/token-expiry-check
chore/upgrade-nx-20
```

## Pull Requests

- Keep PRs focused — one concern per PR
- Link the relevant issue if one exists
- Ensure CI passes before requesting review
- Use the PR template, but keep only the sections that have content — about
  150 words, written for the reviewer. No file-by-file list or restated diff
- Merges are **rebase** merges (squash and merge commits are disabled), so
  every commit reaches `main` as written: tidy the branch into commits that
  each stand alone before asking for review

## AI-Assisted Commits

A commit made with an AI coding agent names the exact agent and model that
ran, in two trailers — the model actually used, never a copied example:

```
Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Assisted-by: Claude Code:claude-opus-5-5
```

(Codex: `Co-Authored-By: Codex <codex@openai.com>` and
`Assisted-by: Codex:<model-id>`.) Attribution lives in commits only: no
"Generated with" footer, robot emoji or attribution line in PR titles, bodies
or comments.

## Code Style

Org-wide standards live in [docs/code-standards.md](docs/code-standards.md) — the contract per-repo linters and CI implement. Each repo enforces its own linting and formatting. Run the relevant checks before opening a PR:

- **apps**: `npx nx lint <project>` · `npx nx test <project>`
- **platform**: `helm lint` + kubeconform via CI
- **infrastructure**: `terraform fmt` · `terraform validate`
- **deployments**: `helm lint` via CI

## Reporting Issues

Use the issue templates — they exist for a reason. Fill them out fully.
