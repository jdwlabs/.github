# Agentic Operating Model

How AI agents author, review, and land changes across the jdwlabs org. This org is one human plus agents: Claude Code sessions author most changes today, an AI-SRE agent responds to cluster alerts, and internal CLIs follow the AXI standard. This doc defines the identity, review, scaling, and safety model that lets agent throughput grow without diluting the guarantees the rulesets already encode.

Current reality this doc starts from (verified against repo settings):

- Every repo's `Baseline` ruleset on `main` requires 1 approving review, strict required status checks, and linear history; `platform`/`infrastructure`/`deployments` add required signatures via `Production Gates`; `deployments` adds a code-owner review gate for prod promotion.
- All PRs are authored under the human's identity with a `Co-Authored-By` agent trailer. Because GitHub forbids self-approval, the 1-review requirement is bypassed with `--admin` merges after in-session review — the review gate exists on paper but is structurally unenforceable with one identity.
- Repos are rebase-merge-only (linear history), which makes concurrent PR landing inherently racy: every merge invalidates every other open PR's "up to date" status.

---

## 1. Identity model for agent-authored PRs

Three options for who an agent's commits and PRs belong to:

| | Human + trailer (today) | Machine user | GitHub App bot |
|---|---|---|---|
| Second identity → real approval flow | No — self-approval impossible, forces `--admin` | Yes | Yes (app reviews count toward required approvals) |
| Verified commits | Yes (human's key) | Yes, once its own SSH/GPG signing key is provisioned | Yes — commits created via the API (`createCommitOnBranch`) are signed by GitHub automatically |
| Credential shape | Human's own auth | Long-lived PAT (rotation burden, broad by default) | Short-lived installation tokens (~1h), permissions scoped per-repo |
| Audit trail | Agent work indistinguishable from human work | Distinct actor, but "was it the agent or a human on the PAT?" is unknowable | Distinct `[bot]` actor; every action attributable to the app |
| Cost / seat | — | Consumes an account; ToS allows one machine user | Free, no seat |
| Kill switch | None short of stopping work | Revoke PAT | Suspend the app installation — one click, org-wide |

The org already has a second account (`jdwlabs-root`), but it is the break-glass admin identity — using an admin account as the everyday bot identity would put maximum privilege behind the highest-volume credential. Keep it as break-glass only.

The one real friction with a GitHub App: agents work in local worktrees, and locally-made commits pushed over git are not signed by the app (apps hold no signing keys). Two workable shapes: (a) push via the GraphQL `createCommitOnBranch` API at the end of a session, which GitHub signs and attributes to the bot — satisfies `Production Gates` required signatures with zero key management; or (b) keep local git push and accept unverified bot commits on repos without required signatures. Start with (a) as the standard push path; it also removes any signing-key material from agent-reachable disk.

With a bot identity the review flow inverts to its intended shape: **agent authors as bot, human reviews and approves as `jdwillmsen`**. The `--admin` bypass stops being routine and becomes an exception that requires recorded justification. The reverse flow (human authors, bot approves) is explicitly out: approval is the one step that must stay human while the org has a single human.

**Recommendation:** Create one org-level GitHub App (`jdwlabs-agent`), installed on all repos, with `contents: write` + `pull_requests: write` and nothing more. Agents author and push as the bot (API-signed commits); the human approves and merges as themselves. Retire routine `--admin` merges; keep `jdwlabs-root` strictly break-glass.

## 2. Review pipeline for agent-authored PRs

Every agent-authored PR passes the same mechanical gates as today (repo CI required checks, security scans). On top of that, review effort is tiered by blast radius, not by diff size:

| Tier | Examples | Automated review | Human role |
|---|---|---|---|
| **T1 — docs/comments** | `docs/`, READMEs, CLAUDE.md, code comments | One review agent (correctness of claims, paths resolve) | Spot-check; approve on green |
| **T2 — code & non-prod config** | app/CLI source, tests, CI workflows, staging values | Code-review agent + security-review agent; Copilot review where enabled | Read the review agents' findings + skim the diff; line-review only flagged hunks |
| **T3 — prod-touching** | prod values/pins, promotion workflows, Terraform, Talos configs, rulesets, secrets plumbing, anything under `deployments` prd paths | Same as T2, plus rendered-manifest / plan diff attached to the PR as evidence | Full line-review of the diff and the rendered/plan output. Never approve on agent summary alone |

Blocking findings, regardless of tier: any security-scan CRITICAL/HIGH without a written justification; any secret detection; any review-agent finding the author-agent neither fixed nor rebutted in-thread. Non-blocking: style nits, speculative refactors — the review agent should not emit them at all (org code standards define the bar; lint enforces style).

Review agents must review the PR as posted (fetch the diff fresh), not the authoring session's claim of what changed — the author-agent summarizing its own work is not review. Findings land as PR review comments so the audit trail lives on the PR, and thread resolution follows the existing standard: every finding fixed or explicitly justified before merge.

**Recommendation:** Adopt the three tiers now, under the current identity model — they don't depend on the bot. Encode the tier in the PR template (author declares it, reviewer confirms). Human line-review is mandatory for T3 and sampled (~1 in 5) for T2 even when agents report clean, to keep the human's model of agent failure modes calibrated.

## 3. Multi-agent scaling

Patterns, in order of current maturity:

- **Parallel worktree agents** (current practice, keep): each agent gets an isolated worktree and branch; never on `main`, never nested, worktree removed after merge. Independent tasks only — two agents editing the same subtree is a scheduling error, not a merge problem to absorb.
- **Background/scheduled agents** (AI-SRE today; more to come): every recurring or long-running loop gets hard caps declared up front — max iterations, token/cost budget, wall-clock limit, and an explicit stop condition. An uncapped loop is a defect. Scheduled agents write their run summary somewhere durable (issue comment, PR, or log the human actually reads), not just session transcripts.
- **Gated shipping**: agent PRs go through the pipeline-style gate (automated review → tests with evidence → lint → push → PR → CI babysit) rather than raw `git push`. The gate is what makes "many agents" safe: it is the same bar regardless of how many sessions are running.

**Landing serialization.** Rebase-only + strict status checks means every merge staling every other open PR. With one or two PRs this is a manual re-rebase; with five agents landing at once it is a retry storm and a race (two PRs both "green" against a `main` neither will actually land on). Two remedies, in order:

1. **Serialize by convention now:** one landing pass at a time — a single session (human or a designated babysit loop) merges ready PRs sequentially, re-rebasing between merges. Agents never merge concurrently with another landing pass.
2. **GitHub merge queue when volume justifies it:** free on public repos, works with required checks and rebase strategy, and turns "up to date" staleness into queue mechanics instead of agent retries. Adopt per-repo, `apps` first (highest PR volume).

**Recommendation:** Keep worktree isolation and hard-capped loops as written rules, adopt serialize-by-convention immediately, and pilot merge queue on `apps` once concurrent agent PRs are routine (more than ~3 open at once regularly).

## 4. Safety rails

Agents may never, autonomously:

- **Mutate prod**: no `terraform apply`/`destroy`, no `talosctl` writes against live nodes, no `kubectl` mutations outside a sanctioned runbook step, no prod promotion merges. Agents plan and diff; a human applies or approves the apply.
- **Handle secret material**: no reading decrypted secret files into context, no `sops -d` output in transcripts, no creating/rotating credentials. Secret changes go through the Vault/SOPS paths with the human executing the sensitive step.
- **Force-push or rewrite shared history**: `main` and release branches are protected by ruleset (non-fast-forward); agents also don't force-push their own PR branches after review has started.
- **Merge with `--admin` (or any bypass)**: bypass merges are human-only, and only with review evidence recorded on the PR. Once the bot identity lands, routine merges need no bypass at all.
- **Alter the guardrails themselves**: rulesets, workflow files that implement gates, CODEOWNERS, app permissions, and this doc are all T3 — agent may propose, human must line-review.

**Attribution:** every agent-driven change is attributable — today via the `Co-Authored-By` trailer, post-bot via the `[bot]` author identity. Incidents caused by agent changes are attributed to the *gate that let them through*, not to "the agent": the postmortem output is a new check, a tier reclassification, or a rails change here — same feedback loop as the code-standards doc.

**Kill switches**, from narrow to broad: stop the session/loop (every loop's hard cap is the passive version); suspend the GitHub App installation (freezes all bot pushes/PRs org-wide in one click); revoke the AI-SRE agent's cluster credentials; disable a repo's auto-triggered workflows. Each switch is documented in an ops runbook with the exact command — a kill switch you have to figure out during an incident is not a kill switch.

**Recommendation:** Treat the five nevers above as org policy effective immediately (they codify current practice), and add the App-suspension runbook entry in the same PR that creates the App.

## 5. Rollout

Smallest-first; each phase is independently valuable and reversible.

1. **Policy on paper (this PR):** tiers, nevers, loop caps, landing serialization — all effective under the current human+trailer model. No new infrastructure.
2. **PR template tier declaration:** add the risk-tier line to the org PR template; reviewers (human or agent) confirm it.
3. **GitHub App identity:** create `jdwlabs-agent`, install org-wide with minimal permissions, wire the API-signed push path into the agent shipping flow on one low-risk repo (`.github` itself), then roll to the rest. Retire routine `--admin` merges as each repo converts.
4. **Review agents as PR actors:** review agents post findings as PR reviews (bot identity), so the audit trail moves from session transcripts to the PR.
5. **Merge queue pilot** on `apps` when concurrent agent PR volume warrants it.
6. **Revisit** after a month of bot-authored PRs: measure `--admin` usage (target: zero routine), review-finding escape rate, and landing friction; adjust tiers and rails from evidence.

**Recommendation:** Ship phases 1–2 now, phase 3 as the next infrastructure ticket, and gate 4–6 on observed volume rather than the calendar.
