# Rulesets

Branch rulesets are managed as code. This document is what the JSON cannot say:
where the files live, what they must all agree on, how to change a required
check without bricking every open pull request, and which parts a person still
has to do by hand.

Companion document: [`branch-protection-bypass.md`](branch-protection-bypass.md)
covers `bypass_actors` — who can step over these rules and why.

## Where the files are

Every repository owns its own rulesets, in its own directory:

```
<repo>/.github/rulesets/
  baseline.json                   # main-branch protection
  branch-naming-convention.json   # conventional branch prefixes
  ...                             # release-tag protection, production gates, ...
  apply.sh                        # pushes the JSON to GitHub
```

**This is deliberate and stays that way.** A ruleset's required status checks
name the CI jobs of the repository it protects, and those legitimately differ:
`infrastructure` requires 4 contexts, `apps` 6, `deployments` 9, `platform` 12.
There is no single ruleset that could be broadcast to all of them, and applying
one repository's `baseline.json` to another would silently delete every context
that repository requires and the recipient does not.

What the per-repository shape cost, until now, was comparability. Five
directories with no shared statement of intent do not drift *from* anything, so
divergence accumulated and read as five deliberate choices.

## The contract

[`.github/rulesets/org-policy.json`](../.github/rulesets/org-policy.json) is the
one statement of what must be true everywhere:

| Requirement | Value |
|---|---|
| `required_approving_review_count` | at least 1 (a `require_code_owner_review` rule counts as 1) |
| `strict_required_status_checks_policy` | `false` |
| Rules present | `pull_request`, `deletion`, `non_fast_forward`, `required_linear_history`, `required_status_checks` |
| Required contexts | `scan / scan`, `scan / gitleaks`, `scan / binaries`, `signatures / signatures` |

Contexts are checked as a **superset**: a repository requiring more of its own
CI than the floor is conforming, not drifting. That is the point of
per-repository rulesets and the check must never argue with it.

### Exceptions

A repository that diverges on purpose declares it, with a reason:

```json
{
  "repo": "deployments",
  "requirement": "min_required_approving_review_count",
  "observed": 0,
  "reason": "Set to 0 by deployments PR #110 ..."
}
```

`observed` pins the exact value being excused, so the exception expires the
moment that value moves — an exception cannot outlive the position it was
written for. An exception matching nothing is reported as a finding rather than
left to rot, and one whose reason is not a reason ("known issue") is rejected
outright. The pattern is borrowed from `deployments`' `tools/prd-drift-holds.yaml`,
for the same reason: a check that cannot express a deliberate state goes red
forever and teaches its reader to skip it.

### What is declared today, and what is not

`deployments` requiring **0** approving reviews is declared. It was set by
`deployments` PR #110 together with a CODEOWNERS that deliberately carries no
catch-all, so the release bot can merge the chart bumps it opens; raising it
would stall that pipeline. `platform`'s
`docs/adr/0018-agentic-app-topology.md` §1 has the full history and reads the
surrounding App bypass as vestigial.

`apps` setting **`strict_required_status_checks_policy: true`** is *not*
declared, and reports as a finding. It has been true since the first
rulesets-as-code commit (`9b51fc1f`, 2026-07-12) — imported from whatever was
live rather than chosen — and no record anywhere says why. That is exactly the
state this check exists to surface: either it is a decision, in which case
somebody writes down what it buys, or it is an import nobody revisited, in which
case it should match everything else. Until one of those happens the check
stays red, which is the correct amount of pressure.

### What a run reports today

Three findings, all verified against live state:

| Repo | Finding | Kind |
|---|---|---|
| `apps` | `strict_required_status_checks_policy: true` | undeclared divergence — decide, then declare or correct |
| `platform` | committed baseline requires `adr-numbering`, live ruleset does not | merged, never applied |
| `platform` | `change-class-review-gate.json` has no live ruleset at all | merged, never applied |

The two `platform` rows need `apply.sh`; the `apps` row needs a decision first.

## Applying

Applying is a manual, post-merge step. Merging a change to a `*.json` file
changes **nothing** on GitHub until somebody runs `apply.sh` with admin on the
target repository.

```bash
./apply.sh                                    # this checkout's repo, this directory
./apply.sh --dry-run                          # diff every export against live, write nothing
./apply.sh --repo jdwlabs/platform --dir ../../../platform/.github/rulesets
./apply.sh --all --workspace ~/projects/jdwlabs
./apply.sh --allow-weakening                  # required.status_checks/approvals/rules would decrease
```

The target repository is read from the checkout's `origin` remote, so a bare
`./apply.sh` is correct wherever the script sits. It used to be a hardcoded
`REPO=` string, which is why each of the five repositories carried its own copy;
with `--repo` and `--dir` one copy drives all of them, and the other four are
redundant.

Five behaviours worth knowing:

- **The whole run is planned before anything is written.** Every export is
  parsed, matched against the live ruleset, and diffed before the first `PUT`
  or `POST` fires; any refusal aborts the run before it writes anything. A run
  that stopped halfway through would leave some repositories reconciled and
  others not, which is the state hardest to notice and hardest to undo.
- **`--dry-run` diffs against live, not just against the last apply.** It pulls
  the ruleset currently in force and shows a unified diff of what would change,
  so it also catches drift nobody applied — an export that already matches live
  is reported `unchanged` and skipped rather than rewritten.
- **A weakening is refused unless `--allow-weakening` says it is deliberate.**
  Removing a required status check, lowering the approval count, dropping a
  rule, or turning enforcement off all count. Step 1 of the rename sequence
  below is exactly this, which is why the flag exists — it turns "someone forgot
  a context was still required" into "someone typed the flag that says this is
  on purpose."
- **Cross-repository applies are refused.** Every export records the repository
  it came from in `source`, and applying it anywhere else stops the run rather
  than skipping the file. `--force` overrides, for the rare case where replacing
  another repository's rules genuinely is the intent.
- **`--all` never broadcasts.** It walks a workspace of checkouts and applies
  each repository's *own* `.github/rulesets` directory to that repository.
  Matching is id, then name, then create: the `id` embedded in an export
  belongs to the repository it was exported from, so if that id is not live on
  the target the script falls back to a ruleset with the same `name` before
  creating — without the name step, applying a file whose ids the target does
  not carry would create a *second* "Baseline" alongside the existing one and
  leave both enforcing.

## Renaming a required check

**This is the part that bites.** A required status check is matched by name. Any
change that renames, merges or removes a CI job has no ordering that avoids a
broken window:

- Merge the workflow change and the ruleset JSON together, and the *live*
  ruleset still demands contexts that no longer exist. The pull request can
  never satisfy them and becomes permanently unmergeable.
- Apply the new ruleset first, and the new context exists on no branch yet, so
  every open pull request is blocked until the workflow change lands.

The supported sequence needs a person with admin at steps 1 and 3:

1. **Apply** with the doomed contexts removed from `required_status_checks`
   (`./apply.sh --allow-weakening` — removing a required check is exactly the
   weakening the script otherwise refuses).
2. **Merge** the workflow pull request that renames the jobs.
3. **Apply** again with the new contexts required — no flag needed, since
   adding a required check only strengthens the ruleset.

Between 1 and 3 those checks are not enforced. Keep the window short, and hold
other merges across it.

### Second consumer: generated PR text

Required-check names are not only in the rulesets.
`deployments/.github/workflows/promote-prd.yml:348` writes the literal string

```
- [ ] CI is green: lint, template (values-prd stack renders), validate-config.
```

into every generated promotion pull request body. A job rename has a text
dependency there too, and nothing will fail if it is missed — the checklist will
simply name checks that no longer exist.

## The reconciliation report

[`.github/workflows/ruleset-reconcile.yml`](../.github/workflows/ruleset-reconcile.yml)
runs `tools/check-ruleset-conformance.py` daily. It **reports and fails; it
never applies.** Two tiers:

| Tier | Question | Token |
|---|---|---|
| committed | Does each checked-in `baseline.json` satisfy the contract? | default `GITHUB_TOKEN` — every repository here is public |
| live | Does each checked-in `baseline.json` match the ruleset in force? | `RULESET_READ_TOKEN` |

The live tier is the one that catches what the manual apply model creates: a
merged JSON edit that nobody applied is enforcing nowhere. It is not
hypothetical — `platform` is in that state twice over. Its committed baseline
requires `adr-numbering` and its live ruleset does not, and its committed
`change-class-review-gate.json` has no live counterpart at all: the file was
merged and never applied, so the gate it describes protects nothing. Neither is
visible from the repository alone, which is the whole argument for this tier.

**The live tier does not run yet.** It needs a secret this repository does not
have. A workflow's own `GITHUB_TOKEN` is scoped to the repository it runs in and
answers 404 for every other repository's rulesets, so the fan-out needs its own
token — the same reason `dependabot-alert-report.yml` carries
`DEPENDABOT_REPORT_TOKEN`.

> **Human step.** Add a repository secret `RULESET_READ_TOKEN` to `jdwlabs/.github`:
> a classic PAT with the `repo` scope, held by an account with admin on all five
> repositories. Reading rulesets needs repository-admin rights, not `admin:org`.

Until that exists the report says `LIVE COMPARISON NOT RUN` in its output and
the job raises a workflow annotation. A tier that did not run is never reported
as a tier that passed.

## Why there are no org-level rulesets

GitHub supports rulesets defined once at the organization level and inherited by
every repository, which would remove most of the above. This org does not use
them, and it is worth recording precisely what is and is not known about why.

`GET /orgs/jdwlabs/rulesets` returns **404**, and `gh` appends a hint about the
`admin:org` scope. That hint has been read as evidence of plan gating. It is
not:

```
HTTP/2.0 404 Not Found
X-Accepted-Oauth-Scopes: admin:org
X-Oauth-Scopes: gist, read:org, repo
```

The token used simply does not carry the scope the endpoint requires, which
explains the 404 completely. The status code carries no additional signal
either, because GitHub is not consistent about it: `GET
/orgs/jdwlabs/actions/permissions` declares the *same*
`X-Accepted-Oauth-Scopes: admin:org` and returns **403**, while
`/orgs/jdwlabs/hooks` returns **404** for a missing `admin:org_hook`. And the
org is not categorically closed to org-level reads — `/orgs/jdwlabs/properties/schema`
returns **200** with that same token.

So: **the 404 is a token-scope artifact and proves nothing about the plan.**
Whether the free plan also gates org-level rulesets is untested here, and
deliberately so — settling it means either granting a token `admin:org` or
attempting a write against org configuration, neither of which is worth doing to
answer a question nothing currently depends on.

Nothing in this design depends on the answer. Repository-level rulesets are what
this org uses, they are available on the free plan for public repositories, and
all five repositories here are public (org plan `free`, 2 filled seats). If
org-level rulesets do turn out to be available, the contract in `org-policy.json`
is the thing that would be promoted into one — which is a reason to keep it
accurate either way.
