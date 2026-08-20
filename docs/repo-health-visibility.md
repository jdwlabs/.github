# Cross-Repo Health Visibility

An audit of the four delivery repositories plus this one, and a decision on
whether the org should run a developer portal, a service catalog, or a
purpose-built dashboard to roll their health up into one view.

**Decision: no new platform.** The org already runs four scheduled cross-repo
reporters. They are the dashboard, badly assembled — separate cadences,
separate tokens, three of the four publishing into a step summary nobody
opens. Consolidating them into one report, and adding the handful of signals
that would have caught this org's actual incidents earlier, costs a workflow
file. Backstage, OpsLevel and Cortex are rejected below with reasons.

**This revises an earlier, heavier build recommendation already on this
ticket, and a follow-up ticket scoped to that heavier build now disagrees
with the decision here — unreconciled; see §9.**

Audited 2026-08-18 against `origin/main` in every repository.

---

## 1. The estate

Four delivery repositories and this meta repository. All public, all on the
GitHub Free plan, all rebase-merge-only, all under one maintainer plus agents.

| | `apps` | `deployments` | `infrastructure` | `platform` |
|---|---|---|---|---|
| Subject | Nx monorepo of applications | GitOps app charts | Talos on Proxmox | Tenant Kubernetes platform |
| Languages | TS/Angular, Go, Java/Kotlin, SQL | Helm YAML, Python, bash | Go, Terraform, Talos YAML | Go, Helm YAML, Python |
| Build | pnpm + Nx | `helm` | `make` + Terraform | `make` + `helm` |
| Workflow files | 6 | 9 | 6 | 8 |
| Test frameworks | Vitest, JUnit, Go, Playwright | Python `unittest`, bash, shellcheck | Go (`-race`) | Go (`-race`), Python `unittest` |
| Coverage measured | no | no | no | no |
| ADR records | 1, still `proposed` | 0 (deliberate) | 0 (deliberate) | 26 |
| Dependency updates | Renovate | Renovate | Renovate | Renovate |
| Blocking security gates | gitleaks, binary size | gitleaks, binary size | gitleaks, binary size | gitleaks, binary size |
| SAST | CodeQL default setup + Trivy | Trivy | Trivy | Trivy |
| SBOM / signing | none | none | none | none |
| Scorecard aggregate | **6.2** | **5.8** | **5.8** | **5.8** |

Uniform across all four, and correctly so: Renovate as the single dependency
owner extending this repo's `default.json`; the reusable `security-scan.yml`
and `verify-pr-signatures.yml` from this repository; rulesets exported as JSON
and re-applied by a checked-in `apply.sh`; an `agent-identity` co-author gate;
`AGENTS.md` as the canonical agent contract with thin `CLAUDE.md`/`GEMINI.md`
pointers; PolyForm NonCommercial licensing; secret scanning and push
protection enabled.

That uniformity is the reason this audit is short. The interesting material is
where the four differ.

## 2. Divergence

### 2.1 Merge gates diverge three ways, and the divergence is not documented

Read live from each repository's rulesets:

| Repository | Approvals required | Branch must be up to date | Own CI jobs required |
|---|---:|---|---|
| `apps` | 1 | **yes** | `main`, `e2e` |
| `deployments` | **0** | no | 5 jobs |
| `infrastructure` | 1 | no | **none** |
| `platform` | 1 | no | 8 jobs |
| `.github` | 1 | no | n/a |

Three findings, in order of severity.

**`infrastructure` requires none of its own checks.** Its Baseline ruleset
requires only the four org-wide contexts — `scan / scan`, `scan / gitleaks`,
`scan / binaries`, `signatures / signatures`. The repository's Go suite, its
`terraform fmt`/`validate` job, and its co-author gate can all be red and the
pull request still satisfies every rule. It is the repository that provisions
the cluster, and it is the only one whose tests are advisory.

**`deployments` requires zero approvals on every ruleset.** The only human gate
is the code-owner requirement on production paths, and its CODEOWNERS
deliberately carries no catch-all so the release bot can land version bumps.
A change outside those paths merges on green CI with no human in the loop at
all. `docs/branch-protection-bypass.md` in this repository justifies the
standing `OrganizationAdmin: always` bypass on the premise that "`Production
Gates` requires one approving review on `refs/heads/main`". In `deployments`
that ruleset requires zero, so the premise does not hold there — the bypass
has nothing to make survivable. That table was verified 2026-08-03 and the
mismatch survived the verification.

**Only `apps` requires branches to be up to date.** `docs/code-standards.md`
§2 states the rule plainly: "requiring branches to be up to date before merging
is what makes the point above mechanical instead of a habit." The point in
question is that a tree-wide gate can be invalidated by any merge, not only a
merge touching the same files. The two repositories that actually run
tree-wide gates — `image-pin-check` in both `platform` and `deployments` — are
the two that do not require up-to-date branches. The repository that does
require it runs no tree-wide gate. The rule is implemented exactly where it
does not apply and omitted exactly where it does.

None of these three is argued for anywhere. Divergence with a reason is fine —
`deployments` and `infrastructure` deliberately keep no ADR directory and
defer to `platform`'s, and that decision is written down. These three are not.

### 2.2 Supply-chain posture is inconsistent with itself

Every repository pins container images hard. `platform` enforces digest
anchoring on every image under `tenants/` and `helm-charts/` with two separate
CI gates and an allowlist that fails when an entry goes stale; `deployments`
pins production images to a tag plus an index digest and fails the promotion
rather than fall back to a bare tag.

No repository pins a GitHub Action by SHA. All four use version tags, and all
four reference this repository's reusable workflows at `@main` — a mutable ref,
consumed by every delivery repository, from the one repository whose README
states that a merge here "takes effect immediately for all callers with no
version bump anywhere". The least-trusted boundary is the least pinned. This is
the single largest contributor to the Scorecard results in §4 and the one
finding where all four repositories are wrong in the same direction.

### 2.3 Coverage is measured nowhere

`apps` wires coverage output directories into roughly twenty project configs,
sets no threshold, and never passes `--coverage` in CI; its Java service has no
JaCoCo. `platform` has a 45:51 test-to-source file ratio and no coverage
tooling. `infrastructure` has 374 test functions and no coverage tooling.
`deployments` has 71 Python test methods and no coverage config.

`docs/code-standards.md` §7 sets a testing bar in terms of behaviour ("new
logic → tests in the same PR") rather than a number, so nothing here violates
the standard. But four repositories independently arriving at "tests yes,
coverage no" is a de facto org position that has never been written down.
Either it is deliberate and belongs in the standards doc, or it is drift.

### 2.4 Documentation gates exist nowhere

No repository runs markdownlint, a link checker, or a prose linter. The only
documentation gate in the org is `platform`'s ADR numbering check. This audit
found stale doc claims in three of four repositories — `apps` README badges
naming Go 1.23 against a 1.26 workspace and Nx 22 against 23.1.1; its
`CONTRIBUTING.md` instructing contributors to squash-merge into a repository
where squash merging is disabled; its devcontainer pinning Go 1.23 and running
`npm ci` in a pnpm-only repository; `platform`'s CODEOWNERS pointing at an ADR
number that a renumbering moved. `docs/code-standards.md` §1 says "Docs are
code. Paths and structure claims in READMEs must resolve in the repo." Nothing
checks that they do.

## 3. What already watches the estate

The org has not built a dashboard. It has built four scheduled reporters, one
at a time, each in response to something that went unnoticed.

| Reporter | Where | Cadence | Scope | Publishes to |
|---|---|---|---|---|
| `dependabot-alert-report.yml` | this repo | weekly | 5 repos | **pinned issue, edited in place** |
| `main-attribution.yml` | this repo | daily | 4 repos | job log / step summary |
| `audit-admin-bypass.yml` | `platform` | daily | 4 repos | step summary |
| `prd-drift.yml` | `deployments` | daily | 1 repo | step summary, fails on drift |

They are individually excellent. `dependabot-alert-report.yml` diffs against
the previous run so a steady count does not read the same as a count with new
highs, carries its state on a workflow artifact to avoid a weekly bookkeeping
commit, and edits one pinned issue rather than appending snapshots.
`main-attribution.yml` refuses to report a pass it did not actually inspect —
an API read failure and a truncated page both exit non-zero rather than
reporting zero findings. `audit-admin-bypass.yml` consults every ruleset
covering the ref and is explicit that its agent-authorship heuristic has false
positives and negatives.

Collectively they have three problems.

**Three of the four publish where nobody looks.** A step summary is visible
only to someone who opens the run. Only the Dependabot report has a durable,
glanceable surface, and its own header comment explains why: the alert backlog
"has been cleared twice and quietly regenerated twice — both times discovered
by accident on a `git push` banner rather than by any mechanism that watches
for it."

**A red scheduled job is indistinguishable from a broken one.**
`deployments`' `prd-drift.yml` has failed on every scheduled run from
2026-08-13 through 2026-08-17. It is failing correctly: production trails the
released `appVersion` by four patch versions on all six charts, the drift-holds
file is empty, and the automatic promotion path is dormant because the E2E
runner is dormant. But a job that is red by design and a job that is red
because it broke look identical from outside, and after five consecutive days
neither reading has produced an action.

**Each carries its own cross-repo credential.** The Dependabot report needs a
PAT because a workflow's default token cannot read another repository's alerts;
`audit-admin-bypass.yml` mints an App token scoped to four repositories. Two
long-lived cross-repo credentials for two reports is twice the blast radius one
report would need.

## 4. OpenSSF Scorecard, measured

Run 2026-08-18 with `gcr.io/openssf/scorecard:stable` (v5.1.1-45-g40bbc9c9)
against each repository's live default branch. These are real results, not an
illustration — re-run 2026-08-20 against the same commits reproduces every
score below, aggregate and per-check. Raw JSON from both runs is attached to
this document's pull request rather than committed to the repository, the
same way every other verification claim in this document is sourced — stated
and dated, not archived as a file.

| Check | `apps` | `deployments` | `infrastructure` | `platform` | `.github` |
|---|---:|---:|---:|---:|---:|
| **Aggregate** | **6.2** | **5.8** | **5.8** | **5.8** | **5.7** |
| Binary-Artifacts | 9 | 10 | 10 | 10 | 10 |
| Branch-Protection | 5 | 3 | 4 | 4 | 4 |
| CI-Tests | 10 | 10 | 10 | 10 | 7 |
| CII-Best-Practices | 0 | 0 | 0 | 0 | 0 |
| Code-Review | 0 | 0 | 0 | 0 | 0 |
| Contributors | 6 | 6 | 3 | 3 | 3 |
| Dangerous-Workflow | 10 | 10 | 10 | 10 | 10 |
| Dependency-Update-Tool | 10 | 10 | 10 | 10 | 10 |
| Fuzzing | 0 | 0 | 0 | 0 | 0 |
| License | 9 | 9 | 9 | 9 | 9 |
| Maintained | 10 | 10 | 10 | 10 | 0 |
| Pinned-Dependencies | 0 | 0 | 0 | 0 | 0 |
| SAST | 10 | 10 | 10 | 10 | 6 |
| Security-Policy | 10 | 10 | 10 | 10 | 10 |
| Signed-Releases | n/a | 0 | 0 | 0 | n/a |
| Token-Permissions | 0 | 0 | 0 | 0 | 6 |
| Vulnerabilities | 7 | 10 | 9 | 10 | 10 |

Read carefully, because three of the zeros are not what they look like.

**`Code-Review` = 0 everywhere is a measurement of the identity model, not of
review.** Scorecard counts changesets that carry an approving review. GitHub
forbids self-approval, the org has one human, so the count is structurally
zero. This is the same fact `docs/agentic-operating-model.md` §1 records as
"the review gate exists on paper but is structurally unenforceable with one
identity", arrived at independently by a tool that knows nothing about this
org. It will move only when a second reviewing identity exists — which is
exactly what that document's phase 3 proposes.

**`Pinned-Dependencies` = 0 everywhere is real and actionable.** It is §2.2:
zero of 22 GitHub-owned and zero of 3 third-party actions pinned by hash in
`platform`, the same shape in the other three, plus unpinned `pip install`
invocations. This is the highest-value single fix Scorecard surfaces.

**`Token-Permissions` = 0 on the four delivery repos is stale relative to the
work already done.** Every workflow in every repository now carries a top-level
`permissions` block, several starting from `permissions: {}` with per-job
grants; the CI audit landed that in August. The score reflects Scorecard's
stricter reading of write-scoped jobs, not an absence of permission blocks.
Worth understanding before treating it as a defect.

**`Fuzzing` = 0 and `CII-Best-Practices` = 0 should be ignored.** Neither is a
sensible target for a homelab platform under one maintainer. A scorecard whose
low numbers are mostly things you have decided not to do is a scorecard that
trains you to skip it.

**`Branch-Protection` 3–5 is the §2.1 finding in Scorecard's vocabulary** —
"branch protection settings apply to administrators is disabled", "up-to-date
branches is disabled", "codeowners review is not required". `deployments`
scores lowest of the four, which is the zero-approvals finding.

The useful move is not to chase the aggregate. It is that Scorecard
independently reproduced three findings this audit reached by hand, for the
cost of one container run. That makes it worth running on a schedule as a
regression check, and it supplies the named industry baseline the CI attribution
work needs.

## 5. What actually went wrong, and what would have caught it

A maturity model would grade this org on fuzzing and best-practice badges. Its
real history points somewhere else. Four incidents, all from the last five
months, all recorded in this org's own tickets and ADRs.

**A release loop ran for twelve days.** A release App's pushes retriggered CI,
the changelog commits made the projects "affected" again, and the preset
patch-bumped on every commit type including its own. It produced roughly 5,465
workflow runs in `apps` across two days, 1,820 bot commits in the last 1,848 on
`main`, and 904 chart-bump commits downstream in `deployments`. It was found by
looking, twelve days in. Baseline org-wide volume today is about 4,400 runs per
thirty days — roughly 147 a day. The loop was running at about 2,700 a day in
one repository. A daily count with a static threshold would have fired on day
one.

**Two chart-release workflows have never run.** `platform`'s and
`deployments`' `release.yml` both trigger on `*-v[0-9]*`, and every chart tag
ever cut in either repository uses `<component>-<version>` with no `v`. Zero
runs, ever, in either repository. No chart has been packaged, no release cut,
and the published Helm index has been hand-edited. Four months. The same
counter that catches a workflow running too often catches one that has never
run at all.

**`main` went red for about fifty minutes, twice, within two minutes.** Two
tree-wide gates were introduced in two repositories minutes apart. Each passed
on its own branch and went red on `main` on the merge commit that introduced
it, so the fix was authored under pressure against a broken trunk. This is why
`docs/code-standards.md` §2 requires up-to-date branches — and why §2.1 above
matters.

**Six consecutive pull requests merged with zero approvals.** Recorded in
`platform`'s ADR on review gates by change class: six of six recent pull
requests merged with `reviewDecision: REVIEW_REQUIRED` via the
`OrganizationAdmin` bypass, and `required_signatures` sat on `main` having
rejected nothing. The bypass is the default path, not break-glass.
`audit-admin-bypass.yml` measures exactly this — into a step summary.

And the near-miss that is the clearest argument of all: secret scanning and
push protection were assumed to be on org-wide because the repositories are
public. `docs/code-scanning-strategy.md` recorded that assumption as something
to verify. It was not verified for months. When someone finally checked, on
2026-07-29, both were disabled on all five repositories. Nothing was watching
the gap between what a document claimed and what the API returned.

Every one of these is a counting problem or a config-drift problem. None of
them is a catalog problem. That is the whole basis of the decision below.

## 6. Where other organizations draw this line

Every first-party account of a developer portal comes from an organization
one to four orders of magnitude larger than this one, and every one names the
same trigger.

| Organization | What they built | Scale stated | Source | Date |
|---|---|---|---|---|
| Spotify | Backstage (open-sourced) | 280 teams, 2,000+ backend services | `engineering.atspotify.com/2020/3/what-the-heck-is-backstage-anyway` | 2020-03-17 |
| Zalando | Sunrise (Backstage-based) | 40,000+ registered entities, replaced "100+ disconnected interfaces" | `engineering.zalando.com/posts/2023/08/sunrise-zalandos-developer-platform-based-on-backstage.html` | 2023-08-03 |
| Monzo | Software Excellence scorecards | 1,800+ microservices | `monzo.com/blog/2021/09/15/how-we-measure-software-excellence` | 2021-09-15 |
| Expedia Group | Backstage (adopted) | 7,000+ components, 4,000+ users | `backstage.io/blog/2023/08/17/expedia-proof-of-value-metrics-2` | 2023-08-17 |
| GitHub (itself) | Flat `SERVICEOWNERS` file + generated CODEOWNERS, deliberately **not** a portal | 4.2M LOC, ~30,000 files | `github.blog/engineering/architecture-optimization/how-we-organize-and-get-things-done-with-serviceowners` | 2023-12-19 |
| Mercedes-Benz.io | Backstage | "hundreds of GitHub organisations" | `mercedes-benz.io/blog/2025-03-14-the-backstage-chronicles-chapter-1` | 2025-03-14 |
| CNOE (Autodesk, Twilio Segment, AWS) | Catalog data-quality practice | — | `cnoe.io/blog/optimizing-data-quality-in-dev-portals` | 2023-11-15 |

Two of those are worth reading past the headline number. GitHub's own
architecture team, at 4.2 million lines of code, chose a glob file plus CI
enforcement over a portal — the strongest anti-portal datapoint available,
from the company that sells the platform this org already runs on. And CNOE
names the maintenance shape that matters more than the initial build: adding
one mandatory catalog field means a pull request against every repository the
catalog covers, a tax that does not amortize with fewer repos — it gets
worse.

Vendor-authored case studies (Hootsuite, BigCommerce, Zapier, Marshmallow —
all OpsLevel or Cortex customer stories, all undated) push the floor lower,
but the smallest of them is still ~40 services and ~50 engineers, and every
one is written by the vendor selling the tool.

The more decisive material is what says *not yet*, from sources with nothing
to sell:

| Source | Finding | Date |
|---|---|---|
| Team Topologies (Thinnest Viable Platform) | "This TVP could be just a wiki page if that's all you need... don't make it any thicker than necessary." | 2019 |
| Thoughtworks Radar — "Incremental developer platform" (Trial) | Start with documentation; add self-service only where it demonstrably pays for itself. | 2022-10-26 |
| Thoughtworks Radar — "Miscellaneous platform teams" (Hold) | Platform work without a clear outcome "struggles to deliver due to high cognitive loads." | 2022-03-29 |
| DORA / Google | 90% of surveyed orgs report an IDP, but platforms follow a J-curve — a throughput and stability dip before any payoff, "if not carefully managed." | 2026-01-12 |
| *Frontiers in Computer Science* (peer-reviewed) | No empirical threshold, at any organization size or service count, where IDP investment is shown to become worthwhile. | 2026-05-04 |
| The Pragmatic Engineer | Places the point where a wiki stops being enough at roughly 30 engineers across 5 product teams. | 2023-02-28 |

No named source puts that line anywhere near four repositories under one
maintainer. More importantly, every named driver — Monzo's, Zalando's,
GitHub's — is **ownership ambiguity across teams and staff turnover**. That
condition does not exist here: one account authored the overwhelming
majority of commits in every repository in this audit. A catalog answers
"who owns this and is it still maintained," and there is only one answer to
give.

## 7. What GitHub already gives away for free

Before comparing tools, the cheapest option is checking what the platform
this org already runs on already provides.

| Feature | Tier required | Available here | Gap |
|---|---|---|---|
| Org Insights (dependency, Actions usage) | GitHub Enterprise Cloud | no — Free plan | — |
| Org Insights — Actions **performance** metrics | GA on all Cloud plans, including Free | **yes** | Run time, queue time, failure rate — no security, no PR age, no dependency staleness |
| Repo Insights (Pulse) | Free | yes | Single repository only — no cross-repo rollup, which is exactly the gap this document is about |
| Projects v2 charts | Free | yes | Charts issues and pull requests only — no workflow runs, no security alerts, no rulesets |
| Repo rulesets + rule-suite audit trail | Free on public repos | yes, already in use | Per-repo only; comparing rulesets across repositories means diffing the API output by hand, which is what §2.1 did |
| Org rulesets | Team/Enterprise | no | — |
| Dependabot alerts, code scanning, secret scanning + push protection | Free on public repos | yes, already on | — |
| Org Security Overview dashboard | Requires Team **and** Code Security add-on | no — not purchasable on this plan without a paid tier | Would add a recurring per-seat and per-committer cost |
| OpenSSF Scorecard | Free, Apache-2.0 | ad hoc only (§4) | Not yet run on a schedule |

The org-wide endpoints the paid Security Overview renders are already free
to call on this plan (`/orgs/{org}/dependabot/alerts`,
`/orgs/{org}/code-scanning/alerts` both return aggregated, org-wide data at
no cost). The only thing a paid tier buys on top of that is a pre-built
screen for data this org can already pull. The genuine gap is presentation
across repositories, not data access — which is the same conclusion §3
reached from the reporter side.

## 8. Market options, and why none of them get adopted

| Option | Cost | What it would cost to run here | Verdict |
|---|---|---|---|
| Backstage (self-hosted) | Free to license | A Node/React monorepo plus a database this org would own; releases monthly and explicitly not semver-versioned; community plugins have been evicted from core before | Maintenance is fixed regardless of repo count — rejected |
| Spotify Portal | Unpublished; still self-run | Same operational shape as Backstage underneath | Cannot even be priced — rejected |
| Cortex | Unpublished, "custom proposal" only | Third-party marketplace data (Vendr) puts the observed median around the tens of thousands per year | Minimum spend far exceeds anything this org's problem justifies — rejected |
| OpsLevel | Unpublished, no self-serve trial | Same marketplace data puts the observed floor in the same range | Same — rejected |
| Port | Free tier: 15 seats, 10k entities, no time limit | Genuinely usable at this scale; the only commercial option not rejected on cost | Still a second control plane and a second auth surface for a problem four workflow files already mostly solve — not adopted, but the one worth re-checking if scale changes |
| Grafana's official GitHub data source | Free, Apache-2.0, actively maintained, self-hosted on infrastructure this org already runs | Ships 24 query types — pull requests, workflow runs, releases, code scanning, Dependabot | Cannot express the join that matters most here: rulesets against actual review counts (§2.1). Fine as a secondary, ad-hoc exploration source; not the backbone |

Nearly every public argument against Backstage is written by a competitor
selling against it, so the fairest case against it is Backstage's own
documentation: monthly non-semver releases and security backports only
"if feasible." That alone is a maintenance commitment with no natural floor,
and this org's actual problem — four uncoordinated reporters, not a missing
catalog — doesn't need one.

## 9. The decision

**No new platform, no new service, and no new long-lived credential.**
Consolidate the four existing reporters (§3) into one scheduled report that
covers all five repositories, publish it to the pattern already proven to
work — a pinned issue, edited in place, the way the Dependabot report
already does it — and add the signals this audit shows are missing from all
four:

- **Per-repo required checks that match each repo's own CI**, closing the
  gap where `infrastructure`'s test suite and every repo's co-author check
  run but block nothing (§2.1).
- **A stated position on branch currency**, so "requires an up-to-date
  branch" lands on the repositories that actually run tree-wide gates
  instead of the one that doesn't (§2.1).
- **A written decision on coverage** — measured with a floor, or explicitly
  not measured and why — so four repositories independently arriving at
  "tests yes, coverage no" stops being unexamined drift (§2.3).
- **Action pins by SHA** in the Renovate config this org already runs
  everywhere, closing the single largest contributor to the Scorecard
  results in §4.
- **A consecutive-failure count, not just a pass/fail line**, so a
  scheduled job that has been red on purpose for five days reads differently
  from one that just broke — the exact ambiguity `prd-drift.yml` sits in
  today. This org has no chat or paging integration to route an alert
  through, so the fix is making the report itself say "N consecutive
  failures" loudly rather than adding a channel that doesn't exist yet.

Scheduling OpenSSF Scorecard itself is not part of this document's scope —
that adoption work is already assigned elsewhere, and this document defers
to it rather than restating it. What is in scope: once it runs on a
schedule, its output is a fifth input the consolidated report above should
carry, for the same reason as everything in the list — §4 showed it
independently reproduces findings this audit reached by hand, for the cost
of one container run.

Grafana's official GitHub data source is worth adding separately and later,
as a free, read-only, ad-hoc exploration surface on top of the observability
stack this org already runs — not as a replacement for the consolidated
report, and not on this ticket's critical path, because it cannot express
the ruleset-versus-review join that §2.1 shows matters most.

Backstage, Cortex, and OpsLevel are rejected outright: no first-party
account exists at anywhere near this scale, the maintenance cost of each is
fixed rather than shrinking with repo count, and the problem every one of
them is built to solve — ownership ambiguity across teams — isn't present
under one maintainer. Port is the one worth re-checking, not adopting now.

**This reverses an earlier build recommendation, and that reversal is not
yet reconciled.** An earlier, read-only pass through this same question
recommended the opposite shape of build: a small in-cluster exporter
publishing to the Prometheus this org already runs, a Grafana dashboard, and
Alertmanager rules — and a follow-up ticket was filed for exactly that. This
document's audit went further before reaching a decision: §3 established
that four scheduled reporters already exist and the missing piece is a
durable, glanceable sink, not another collector, and §6 confirmed that the
condition every named source cites for adopting heavier tooling — ownership
ambiguity across teams — is absent here at any weight of build. Folding the
existing reporters into one report costs a workflow file; standing up an
exporter, a dashboard, and alert rules is more machinery for the same
handful of counters. The earlier follow-up ticket is scoped to the heavier
build this document declines to recommend. It has not been edited or closed
as part of this audit — rescoping someone else's ticket is out of bounds for
a research pass — but it now disagrees with the decision above, and it needs
reconciling against this document before it is picked up, not discovered
mid-implementation. That reconciliation is recorded on both tickets, not
resolved here.

**Revisit this decision when a second human maintainer with write access
joins.** That is the trigger every primary source in §6 actually names, not
a repo count.

