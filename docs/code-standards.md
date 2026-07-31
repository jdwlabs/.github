# jdwlabs Code Standards

The org-wide contract for code quality. Per-repo linters and CI implement it mechanically; PR review covers the judgment calls tools can't. If a rule here conflicts with a repo's committed lint config on a style specific, the lint config wins for that repo — then fix this doc or the config so they agree. Missing enforcement (a required check a repo doesn't run yet) is a gap to ticket, never an exemption.

How this is enforced (standard GitHub layering):

| Layer | Mechanism | Where |
|---|---|---|
| Org contract | This doc + [CONTRIBUTING](../CONTRIBUTING.md) | `jdwlabs/.github` |
| Mechanical checks | Linters/formatters committed per repo | each repo |
| Gates | CI required checks + reusable workflows | `.github/workflows/`, org `security-scan.yml` |
| Review routing | CODEOWNERS + branch rulesets | each repo |
| Judgment | PR review against this doc | humans + review agents |

---

## 1. Universal (every file, every repo)

- **Comments explain *why*, never *what*.** Self-documenting code first. Comment only: workarounds (with cause), surprising decisions, invariants/units, security/concurrency caveats. Match surrounding comment density.
- **No tracker references in code or manifest comments** — no `JDWLABS-*`, issue/PR numbers, or URLs-as-traceability. Traceability lives in commit messages and PR descriptions, where `git blame`/`git log` finds it. Applies to YAML/Helm values and raw manifests, not just source.
- **Never commit commented-out code.** Delete it; git remembers.
- **Secrets never in git.** Runtime secrets: Vault → External Secrets Operator. Infra-at-rest: SOPS + age (`*.enc.yaml` only). Every repo's `.gitignore` covers `.env*`, `*.key`, `*.pem`, kubeconfig/talosconfig paths.
- **Docs are code.** Paths and structure claims in READMEs/CLAUDE.md/AGENTS.md must resolve in the repo. Stale docs are bugs — fix in the same PR that moves things.
- **License:** PolyForm Noncommercial 1.0.0 across org repos.

## 2. Git & Delivery

- Conventional Commits (types/format in [CONTRIBUTING](../CONTRIBUTING.md)); branch names `<type>/<kebab-description>`.
- `main` is a merge target only — everything lands via PR with green CI. No direct pushes.
- Linear history preferred; repos declare their merge strategy (apps: rebase-only).
- PRs: one concern, template filled, linked ticket where one exists, every review thread and bot/security finding fixed or explicitly justified before merge.
- Commits signed and verified on GitHub (noreply email UID). History backfills in progress do not exempt new commits.

### Tree-wide gates

A **tree-wide gate** is any check whose result depends on files the pull request does not modify — it scans the repository, not the diff. Today's examples: `image-pin-check` (platform `Validate`, deployments `CI`), and the `extraManifests` pin test in infrastructure `Bootstrap`.

Any merge to `main` can invalidate one, not only a merge touching the same files. **Green on the branch is not green on the merge result.** Two such gates, introduced within two minutes of each other, each passed on its own branch and went red on `main` on the merge commit that introduced it — `main` stayed red for about fifty minutes in both repos, so the fix was authored under pressure against a broken trunk.

- A tree-wide gate runs on `pull_request` with **no `paths:` filter**. A path filter hides the gate on exactly the pull requests most likely to invalidate it, and makes the check unusable as a required one: a required check that never reports leaves every unrelated pull request permanently pending.
- Before merging, rebase onto `origin/main` and confirm the pull request's own run is against the current tip. A green run against a superseded tip is evidence about a tree that no longer exists.
- Requiring the check is what makes the gate blocking; requiring branches to be up to date before merging is what makes the point above mechanical instead of a habit. A gate no ruleset requires is advisory, whatever its name suggests.

## 3. Go (`platformctl`, `talops`, backend services)

- `gofmt` + `goimports` clean; repo `.golangci.yml` is the lint contract and CI must run `golangci-lint run` as a required check.
- `go test -race ./...` green — race detector always, not optionally.
- Table-driven tests; fake clients (e.g. `k8s/fake.go` pattern) over mock frameworks; testdata fixtures for parsing/validation.
- Errors wrapped with context: `fmt.Errorf("doing X: %w", err)`. No swallowed errors — handle, return, or log with reason.
- Structured logging (zap); no `fmt.Println` in production paths.
- Layout: `cmd/` thin, logic in `internal/` packages; Cobra command tree.
- **Agent-facing CLIs follow AXI**: TOON output, minimal default schemas, structured errors to stdout, exit codes `0`/`1`, definitive empty states, never block on interactive prompts in CI/agent contexts.

## 4. TypeScript / Angular / Nx (`apps`)

- ESLint flat config (`eslint.config.ts`) + Prettier (repo `.prettierrc`) — CI runs `nx format:check` and `nx affected -t lint`.
- TypeScript strict; no `any` without an inline why-comment.
- Modern Angular: standalone components, signals-first, DI tokens for environment config; no new NgModules.
- **Every Nx project carries `type:`/`scope:`/`framework:` tags, and module boundaries (`depConstraints`) enforce them.** Layering: app → feature → ui/data-access → util; feature scopes import only self + shared.
- Tests: Vitest for unit, Playwright for e2e; new logic ships with tests in the same PR.
- Conventional commits enforced by commitlint (husky `commit-msg`).

## 5. Helm / Kubernetes / YAML (`platform`, `deployments`)

- `yamllint`, `helm lint`, and `helm template | kubeconform` (with CRD schemas) must all run and pass in CI — rendering to /dev/null without schema validation does not count.
- **Every workload sets resource requests and limits** — no BestEffort pods (a node roll OOM-killing unbounded pods is a learned incident, not a hypothetical).
- **Probes required:** liveness + readiness always; `startupProbe` for slow-boot workloads (JVMs) so CPU-limit changes can't fail liveness during boot.
- Security contexts: non-root, no privilege escalation, unless documented why.
- `Chart.yaml version` = chart packaging changes only. Never mirror image tags into it; prod pins live in `values-<env>.yaml`.
- Shared scaffolding goes in a library chart — no copy-paste chart-per-app.
- Values comments explain why a value diverges (workaround, incident note), never restate the key.

## 6. Terraform / Talos (`infrastructure`)

- `terraform fmt -check` + `validate` in CI; providers must be version-pinned and `.terraform.lock.hcl` must be committed (not gitignored).
- Remote, locked state backend — never local state on a workstation.
- Repeated resources use modules/`for_each`, not duplicated files.
- Applies are human-gated: agents plan, humans apply. Never autonomous `apply`/`destroy`.
- Version pins in repo match the running cluster (drift is a bug); Talos/K8s versions pinned by digest where supported.

## 7. Testing Bar (org-wide)

- New logic → tests in the same PR. Bug fix → regression test that fails without the fix, where a test surface exists.
- No skipped/`only`'d tests on `main`.
- E2E covers the deployed surface (staging Playwright gate on deploy dispatch).

## 8. Documentation & Decisions

- Every repo: accurate README structure section, `CONTRIBUTING` (org-level fallback), agent docs (one canonical file; others point to it).
- Recurring operations get runbooks (`scenarios/`, `docs/OPERATIONS.md` pattern); incidents feed runbooks.
- Design decisions worth revisiting get a dated spec/ADR committed to the repo — not local-only notes.

## 9. Definition of Done (org-wide)

A change is Done when: deliverables verified with evidence; merged to `main` via green-CI PR; review threads and security findings resolved or justified; lint/format/test gates green; docs and runbooks updated where behavior changed; for GitOps changes, ArgoCD Synced + Healthy verified against the live cluster. The Jira workflow expands this per issue type.

## 10. Improving This Document

This is a living contract, not a monument.

- **Feedback loop:** every incident, review finding, or retro that exposes a missing/wrong rule produces a PR here in the same week — with the evidence in the PR description, not in the doc.
- **Requirements vs reality:** this doc states requirements. Where a repo doesn't yet comply, open a ticket for the gap; never soften the rule to match the gap. Known gaps at last audit (2026-07-10): platform CI doesn't run golangci-lint; deployments CI skips kubeconform; infrastructure gitignores the Terraform lockfile; apps commit-signing backfill in flight.
- **Cadence:** re-audit this doc against the repos whenever a new repo or stack joins the org, and at least quarterly — a rule nobody has checked in a quarter is a rumor.
- **Change process:** PR to `jdwlabs/.github`, one concern per change, rationale in the PR. Silence is agreement; objections belong on the PR, not in side channels.

