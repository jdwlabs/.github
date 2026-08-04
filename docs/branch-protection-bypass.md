# Branch Protection Bypass

Every ruleset export in this org carries a `bypass_actors` list, and a bypass
reads as an oversight unless something says otherwise. This document is that
something: what can bypass branch protection today, why each entry is there,
and what would have to change for it to go away.

Rulesets themselves are managed as code — `.github/rulesets/*.json` in each
repository, applied by the `apply.sh` next to them. They are JSON and cannot
carry comments, which is why the reasoning lives here.

## Live state

Verified 2026-08-03 against the live rulesets in all five repositories.

| Repository | Ruleset | OrganizationAdmin | Release App (`4065387`) |
|---|---|---|---|
| `apps` | Baseline | `always` | **`always`** |
| `apps` | Branch Naming Convention | `always` | — |
| `apps` | Release Tag Protection | `always` | — |
| `apps` | Code Quality Copilot review | — | — |
| `platform` | Baseline | `always` | — |
| `platform` | Production Gates | `always` | — |
| `platform` | Branch Naming Convention | `always` | — |
| `platform` | Release Tag Protection | `always` | — |
| `infrastructure` | Baseline | `always` | — |
| `infrastructure` | Production Gates | `always` | — |
| `infrastructure` | Branch Naming Convention | `always` | — |
| `infrastructure` | Release Tag Protection | `always` | — |
| `deployments` | Baseline | `always` | `pull_request` |
| `deployments` | Production Gates | `always` | `pull_request` |
| `deployments` | PRD Promotion Review Gate | `always` | `pull_request` |
| `deployments` | Branch Naming Convention | `always` | — |
| `deployments` | Release Tag Protection | `always` | — |
| `.github` | Baseline | `always` | — |
| `.github` | Branch Naming Convention | `always` | — |

The two bypass modes are not the same permission. `always` exempts the actor
from the rule however the change arrives, including a direct push to the
protected branch. `pull_request` exempts it only when the change arrives as a
pull request — the branch itself stays unpushable. Only the first of those can
put a commit on `main` that no pull request ever describes.

## `OrganizationAdmin: always` — accepted

This is the load-bearing one, and it is deliberate.

`Production Gates` requires one approving review on `refs/heads/main`, and
`.github/CODEOWNERS` is a catch-all (`* @jdwillmsen`). GitHub does not let an
author approve their own pull request. With a single maintainer holding every
role, an unbypassed rule is not a stricter rule — it is a repository in which
nothing can be merged at all. The bypass is what makes the review requirement
survivable rather than what makes it toothless; without it the requirement
would have had to be deleted instead, which is strictly worse because it would
also stop applying the moment a second reviewer exists.

What it costs: for that one account, the gates are advisory. Required status
checks, required reviews, and linear history can all be stepped over, and a
commit can reach `main` without a pull request at all.

What limits the cost in practice:

- Work still goes through pull requests by convention, so the checks still run
  and are still read. The bypass is an escape hatch, not the normal path.
- The `main` attribution check (`main-attribution.yml`) reports any commit on
  a default branch that no merged pull request accounts for. It cannot prevent
  the push, but it means an exercised bypass is visible rather than silent.

**Revisit when a second maintainer with write access exists.** At that point
the review requirement is satisfiable by a person, and this entry should be
narrowed to `pull_request` or dropped entirely.

There is a narrowing available before that: `pull_request` mode would keep the
solo-maintainer merge path working while making direct pushes to `main`
impossible. It has not been applied because the merge path is the one thing
that must not break, and the change is only safe to make immediately before a
merge that can verify it. Recorded here as the next step rather than as a
finding.

## `Integration/4065387: always` on `apps` — temporary

The release App holds unconditional bypass on `apps` only. It is exercised on
every release: `nx release` commits the version bump and points the release
tags at that commit, so the commit must exist on `main` before the tags can be
pushed, and no pull request can sit in between. `7928eb1f`
(`chore(release): publish [skip ci]`, 2026-08-02) is one such commit — single
parent, committed by `github-actions[bot]`, zero associated pull requests,
where every other commit around it on `main` has exactly one.

`deployments` used to have the same entry and no longer needs it. Chart bumps
now go through the API on a `chore/<project>-appversion-<version>` branch, with
a pull request, checks, a merge, and a read-back of `main` to confirm the bump
landed — so `pull_request` mode is sufficient there.

`apps` cannot make the same move while the version is sourced from the commit.
Re-sourcing release versions from the git tags removes the need for the
version commit to land first, which is what makes this entry removable. That
work is tracked as JDWLABS-273.

Until then `apps` is **excluded from the `main` attribution check**. The
alternative was an allowlist keyed on committer name and message prefix, which
`verify-pr-signatures.yml` already rejects for good reason: an allowlist keyed
on an attacker-supplied field is a hole that anything claiming that field walks
straight through. A check that is expected to be red every release is also a
check that stops being read.

**Revisit when JDWLABS-273 lands.** Removing this entry and adding `apps` to
the attribution check are the same change.
