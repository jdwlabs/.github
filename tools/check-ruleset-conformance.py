#!/usr/bin/env python3
"""Report repositories whose Baseline ruleset diverges from the org contract.

Branch rulesets in this org are managed as code, one `.github/rulesets/`
directory per repository, and that is the right shape: required status checks
name the CI jobs of the repository they protect, and the four delivery repos
legitimately require between 4 and 13 different contexts. What was missing is
anything that compares them. Five independent directories with no shared
statement of intent do not drift *from* anything — there was nothing to drift
from — so divergence accumulated silently and read as five deliberate choices.

It is not five deliberate choices. Measured across the org, `deployments`
requires 0 approving reviews where every other repository requires 1, and
`apps` sets `strict_required_status_checks_policy: true` where every other
repository leaves it false. One of those has a recorded reason and one does
not, and until this check existed there was no way to tell which was which.
That is the whole value on offer: not enforcement, but making an undeclared
divergence impossible to mistake for a decision.

`.github/rulesets/org-policy.json` is the contract. It states only the
invariants that must hold everywhere and deliberately says nothing about the
per-repository required contexts, which are checked as a *superset* — a
repository requiring more of its own CI than the org minimum is conforming, not
drifting.

An exception is how a repository says "this divergence is a decision". It
carries a mandatory reason and the exact value it excuses, so it expires the
moment that value moves — an exception cannot outlive the position it was
written for, and one matching nothing is reported rather than left to rot. This
matters more than it sounds here: `deployments`' 0 exists because a pull request
put it there to unblock the release bot, and a checker that "reconciled" it to
1 would break that pipeline while reporting success.

Two tiers, because they answer different questions and need different tokens:

  * committed — does each repository's checked-in `baseline.json` satisfy the
    contract? Needs no privileged token; every repository here is public.
  * live — does each repository's checked-in `baseline.json` match the ruleset
    actually in force? Needs a token with admin read on each repository, which
    a workflow's own `GITHUB_TOKEN` is not. This is the tier that catches the
    failure mode the apply model creates: applying is a manual, post-merge
    step, so a merged JSON edit that nobody applied is live nowhere. `platform`
    is in exactly that state twice over — its committed baseline requires
    `adr-numbering` and ruleset 17653707 does not, and its committed
    `change-class-review-gate.json` has no live counterpart at all.

The live tier is skipped, loudly and in the summary, when no such token is
present. A tier that did not run is never reported as a tier that passed.

Usage:
    python3 tools/check-ruleset-conformance.py [--policy PATH] [--repo NAME]
                                               [--no-live] [--json]

Exit codes: 0 = every repository conforms and every exception is live;
1 = a divergence, a stale exception, or a committed/live mismatch;
2 = the check could not reach a verdict (unreadable policy, API failure).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY = REPO_ROOT / ".github/rulesets/org-policy.json"

# 0 and 1 are verdicts — conforming, or diverged. 2 says no verdict was reached,
# so a caller never has to read "the check failed" as "the check found
# something".
EXIT_CONFORMING = 0
EXIT_DIVERGED = 1
EXIT_NO_VERDICT = 2

# Environment variables consulted, in order, for a token that can read rulesets.
# A workflow's default GITHUB_TOKEN is scoped to the repository it runs in and
# returns 404 for every other repository's rulesets, so it is deliberately not
# in this list — using it would turn "cannot see" into "nothing to see".
LIVE_TOKEN_VARS = ("RULESET_READ_TOKEN", "GH_RULESET_TOKEN")


class ToolError(Exception):
    """The check could not run — distinct from "the check found something"."""


@dataclass
class Report:
    findings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    live_checked: list[str] = field(default_factory=list)
    live_skipped_reason: str | None = None

    @property
    def conforming(self) -> bool:
        return not self.findings


def gh_json(args: list[str], token: str | None = None) -> object:
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token
        env.pop("GITHUB_TOKEN", None)
    result = subprocess.run(["gh", *args], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise ToolError(f"gh {' '.join(args)}\n{result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ToolError(f"gh {' '.join(args)} returned non-JSON output: {exc}") from exc


def gh_raw(args: list[str], token: str | None = None) -> str:
    env = dict(os.environ)
    if token:
        env["GH_TOKEN"] = token
        env.pop("GITHUB_TOKEN", None)
    result = subprocess.run(["gh", *args], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise ToolError(f"gh {' '.join(args)}\n{result.stderr.strip()}")
    return result.stdout


def load_policy(path: Path) -> dict:
    try:
        policy = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise ToolError(f"{path}: not found") from exc
    except json.JSONDecodeError as exc:
        raise ToolError(f"{path}: not valid JSON — {exc}") from exc

    for key in ("owner", "repos", "baseline", "requirements"):
        if key not in policy:
            raise ToolError(f"{path}: missing required key {key!r}")
    if not policy["repos"]:
        raise ToolError(f"{path}: declares no repositories")

    for index, exception in enumerate(policy.get("exceptions", [])):
        for key in ("repo", "requirement", "observed", "reason"):
            if key not in exception:
                raise ToolError(
                    f"{path}: exceptions[{index}] is missing {key!r} — an exception "
                    "without all four cannot be checked or understood later"
                )
        # A reason is the entire point of an exception. "Known issue" is not a
        # reason; the next reader has to be able to decide whether it still
        # applies without asking whoever wrote it.
        if len(str(exception["reason"]).split()) < 8:
            raise ToolError(
                f"{path}: exceptions[{index}] ({exception['repo']}/"
                f"{exception['requirement']}) has no usable reason"
            )
    return policy


def exception_for(policy: dict, repo: str, requirement: str) -> dict | None:
    for exception in policy.get("exceptions", []):
        if exception["repo"] == repo and exception["requirement"] == requirement:
            return exception
    return None


def rules_of_type(document: dict, rule_type: str) -> list[dict]:
    return [rule for rule in document.get("rules", []) if rule.get("type") == rule_type]


def covers_ref(document: dict, ref: str) -> bool:
    includes = document.get("conditions", {}).get("ref_name", {}).get("include", [])
    return ref in includes or "~DEFAULT_BRANCH" in includes or "~ALL" in includes


def approval_count(document: dict) -> int | None:
    """Approvals the pull_request rule demands, or None if there is no such rule.

    A code-owner requirement scores as one approval even where the rule's own
    count is zero: GitHub folds CODEOWNERS into the review decision, so a rule
    needing an owner's sign-off does demand a review regardless of the number.
    """
    counts = []
    for rule in rules_of_type(document, "pull_request"):
        params = rule.get("parameters", {})
        count = params.get("required_approving_review_count", 0)
        if params.get("require_code_owner_review"):
            count = max(count, 1)
        counts.append(count)
    return max(counts) if counts else None


def status_check_rule(document: dict) -> dict | None:
    rules = rules_of_type(document, "required_status_checks")
    return rules[0]["parameters"] if rules else None


def check_document(repo: str, document: dict, policy: dict, consumed: set) -> list[str]:
    """Findings for one repository's baseline against the contract."""
    findings = []
    requirements = policy["requirements"]
    ref = policy["baseline"]["ref"]
    where = f"{repo}: {policy['baseline']['path']}"

    if document.get("enforcement") != "active":
        findings.append(
            f"{where} enforcement is {document.get('enforcement')!r}, not 'active' — "
            "a ruleset that is not enforcing protects nothing"
        )

    if not covers_ref(document, ref):
        findings.append(
            f"{where} does not cover {ref} (covers "
            f"{document.get('conditions', {}).get('ref_name', {}).get('include', [])}) — "
            "every other check below is measured against a branch this ruleset "
            "does not protect"
        )

    present = {rule.get("type") for rule in document.get("rules", [])}
    for rule_type in requirements["required_rule_types"]:
        if rule_type not in present:
            findings.append(f"{where} is missing the {rule_type!r} rule")

    minimum = requirements["min_required_approving_review_count"]
    actual = approval_count(document)
    if actual is None:
        if "pull_request" in present:
            findings.append(f"{where} has a pull_request rule with no parameters")
    elif actual < minimum:
        exception = exception_for(policy, repo, "min_required_approving_review_count")
        if exception is None:
            findings.append(
                f"{where} requires {actual} approving review(s), the contract "
                f"requires at least {minimum}. Either raise it, or declare the "
                f"divergence in {DEFAULT_POLICY.name} with the reason it stands"
            )
        elif exception["observed"] != actual:
            findings.append(
                f"{where} requires {actual} approving review(s) but its declared "
                f"exception excuses {exception['observed']} — the value moved and "
                "the exception no longer describes it"
            )
        else:
            consumed.add((repo, "min_required_approving_review_count"))

    params = status_check_rule(document)
    if params is None:
        if "required_status_checks" in present:
            findings.append(f"{where} has a required_status_checks rule with no parameters")
    else:
        expected_strict = requirements["strict_required_status_checks_policy"]
        actual_strict = params.get("strict_required_status_checks_policy", False)
        if actual_strict != expected_strict:
            exception = exception_for(policy, repo, "strict_required_status_checks_policy")
            if exception is None:
                findings.append(
                    f"{where} sets strict_required_status_checks_policy="
                    f"{str(actual_strict).lower()}, the contract says "
                    f"{str(expected_strict).lower()}. Either match it, or declare the "
                    f"divergence in {DEFAULT_POLICY.name} with the reason it stands"
                )
            elif exception["observed"] != actual_strict:
                findings.append(
                    f"{where} sets strict_required_status_checks_policy="
                    f"{str(actual_strict).lower()} but its declared exception excuses "
                    f"{str(exception['observed']).lower()} — the value moved and the "
                    "exception no longer describes it"
                )
            else:
                consumed.add((repo, "strict_required_status_checks_policy"))

        # A superset is conforming. Repository-specific contexts are the point of
        # per-repository rulesets; only the org-wide floor is contractual.
        contexts = {check.get("context") for check in params.get("required_status_checks", [])}
        missing = [c for c in requirements["required_status_check_contexts"] if c not in contexts]
        if missing:
            findings.append(
                f"{where} does not require the org-wide context(s): {', '.join(missing)}"
            )

    return findings


def summarize(document: dict) -> dict:
    """The dimensions a reader cares about, flattened for a readable diff."""
    params = status_check_rule(document) or {}
    return {
        "enforcement": document.get("enforcement"),
        "refs": sorted(document.get("conditions", {}).get("ref_name", {}).get("include", [])),
        "rules": sorted(rule.get("type") for rule in document.get("rules", [])),
        "approvals": approval_count(document),
        "strict": params.get("strict_required_status_checks_policy"),
        "contexts": sorted(
            check.get("context") for check in params.get("required_status_checks", [])
        ),
        "bypass_actors": sorted(
            f"{actor.get('actor_type')}:{actor.get('actor_id')}:{actor.get('bypass_mode')}"
            for actor in document.get("bypass_actors", [])
        ),
    }


def summary_differences(committed: dict, live: dict) -> list[str]:
    differences = []
    left, right = summarize(committed), summarize(live)
    for key in left:
        if left[key] == right[key]:
            continue
        if isinstance(left[key], list):
            only_committed = [v for v in left[key] if v not in right[key]]
            only_live = [v for v in right[key] if v not in left[key]]
            parts = []
            if only_committed:
                parts.append(f"committed-only: {', '.join(map(str, only_committed))}")
            if only_live:
                parts.append(f"live-only: {', '.join(map(str, only_live))}")
            differences.append(f"{key}: {'; '.join(parts)}")
        else:
            differences.append(f"{key}: committed={left[key]!r} live={right[key]!r}")
    return differences


def fetch_committed(owner: str, repo: str, path: str, token: str | None = None) -> dict:
    raw = gh_raw(
        [
            "api",
            f"repos/{owner}/{repo}/contents/{path}",
            "-H",
            "Accept: application/vnd.github.raw",
        ],
        token=token,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ToolError(f"{owner}/{repo}:{path} is not valid JSON — {exc}") from exc


def fetch_live_listing(owner: str, repo: str, token: str) -> list[dict]:
    listing = gh_json(["api", f"repos/{owner}/{repo}/rulesets"], token=token)
    if not isinstance(listing, list):
        raise ToolError(f"{owner}/{repo}: rulesets endpoint returned {type(listing).__name__}")
    # Org-level rulesets can appear here but cannot be updated through the
    # repository endpoint, so they are not what any committed export describes.
    return [entry for entry in listing if entry.get("source_type") == "Repository"]


def fetch_live_detail(owner: str, repo: str, listing: list[dict], name: str, token: str) -> dict:
    matches = [entry for entry in listing if entry.get("name") == name]
    if not matches:
        raise ToolError(
            f"{owner}/{repo}: no repository ruleset named {name!r} is live "
            f"(saw: {', '.join(sorted(str(e.get('name')) for e in listing)) or 'none'})"
        )
    detail = gh_json(["api", f"repos/{owner}/{repo}/rulesets/{matches[0]['id']}"], token=token)
    if not isinstance(detail, dict):
        raise ToolError(f"{owner}/{repo}: ruleset detail returned {type(detail).__name__}")
    return detail


def committed_ruleset_names(owner: str, repo: str, directory: str) -> dict[str, str]:
    """Every ruleset name the repository has checked in, mapped to its filename.

    Only files carrying a `target` count; anything else in that directory is
    configuration rather than a ruleset to apply — the same test apply.sh uses.
    """
    listing = gh_json(["api", f"repos/{owner}/{repo}/contents/{directory}"])
    if not isinstance(listing, list):
        raise ToolError(f"{owner}/{repo}:{directory} is not a directory")

    names = {}
    for entry in listing:
        filename = entry.get("name", "")
        if entry.get("type") != "file" or not filename.endswith(".json"):
            continue
        document = fetch_committed(owner, repo, f"{directory}/{filename}")
        if document.get("target") and document.get("name"):
            names[document["name"]] = filename
    return names


def unapplied_rulesets(owner: str, repo: str, directory: str, listing: list[dict]) -> list[str]:
    """Committed rulesets with no live counterpart of the same name.

    A file that was merged and never applied is enforcing nothing at all — a
    stronger version of the same failure as a ruleset whose live copy is merely
    out of date, and invisible from the repository alone.
    """
    live_names = {entry.get("name") for entry in listing}
    committed = committed_ruleset_names(owner, repo, directory)
    return [f"{filename} ({name!r})" for name, filename in sorted(committed.items())
            if name not in live_names]


def live_token() -> tuple[str | None, str]:
    for name in LIVE_TOKEN_VARS:
        value = os.environ.get(name)
        if value:
            return value, name
    return None, ""


def run(policy: dict, repos: list[str], want_live: bool) -> Report:
    report = Report()
    owner = policy["owner"]
    path = policy["baseline"]["path"]
    name = policy["baseline"]["ruleset_name"]
    consumed: set = set()

    token, token_var = live_token()
    if not want_live:
        report.live_skipped_reason = "--no-live was passed"
    elif token is None:
        report.live_skipped_reason = (
            "no ruleset-read token in the environment (looked for "
            f"{', '.join(LIVE_TOKEN_VARS)}). A workflow's own GITHUB_TOKEN cannot "
            "read another repository's rulesets, so the committed-versus-live "
            "comparison did not run — this run says nothing about whether the "
            "rulesets in force match the JSON in git"
        )

    for repo in repos:
        # Failure to read is not a pass. Left unchecked, an API error yields no
        # findings and a green tick over a repository nothing looked at.
        document = fetch_committed(owner, repo, path)
        report.checked.append(repo)
        report.findings.extend(check_document(repo, document, policy, consumed))

        if report.live_skipped_reason is None:
            listing = fetch_live_listing(owner, repo, token)
            live = fetch_live_detail(owner, repo, listing, name, token)
            report.live_checked.append(repo)
            differences = summary_differences(document, live)
            if differences:
                report.findings.append(
                    f"{repo}: the committed {path} is not what is live — "
                    + "; ".join(differences)
                    + ". Applying is a manual post-merge step, so a merged edit "
                    "that nobody applied is enforcing nowhere"
                )
            unapplied = unapplied_rulesets(owner, repo, path.rsplit("/", 1)[0], listing)
            if unapplied:
                report.findings.append(
                    f"{repo}: committed but live nowhere — {', '.join(unapplied)}. "
                    "The file was merged and never applied, so it protects nothing"
                )

    for exception in policy.get("exceptions", []):
        key = (exception["repo"], exception["requirement"])
        if exception["repo"] not in repos:
            report.notes.append(
                f"exception {key[0]}/{key[1]} not evaluated — {key[0]} was not in this run's scope"
            )
        elif key not in consumed:
            report.findings.append(
                f"stale exception: {key[0]}/{key[1]} excuses "
                f"{json.dumps(exception['observed'])}, which is no longer what {key[0]} has. "
                "Remove it — an exception nothing matches is a claim nobody rechecked"
            )

    return report


def print_report(report: Report, policy: dict) -> None:
    print(f"checked {len(report.checked)} repositories against {DEFAULT_POLICY.name}: "
          f"{', '.join(report.checked)}")
    if report.live_skipped_reason:
        print(f"LIVE COMPARISON NOT RUN — {report.live_skipped_reason}")
    else:
        print(f"live comparison ran for: {', '.join(report.live_checked)}")

    declared = policy.get("exceptions", [])
    if declared:
        print(f"\ndeclared exceptions ({len(declared)}):")
        for exception in declared:
            observed = json.dumps(exception["observed"])
            print(f"  {exception['repo']}/{exception['requirement']} = {observed}")
            print(f"    {exception['reason']}")

    for note in report.notes:
        print(f"\nnote: {note}")

    if report.findings:
        print(f"\nFINDINGS ({len(report.findings)}):")
        for finding in report.findings:
            print(f"  - {finding}")
        print(
            "\nEach finding is either a value to correct or a decision to declare in "
            f"{policy['baseline']['path'].rsplit('/', 1)[0]}/{DEFAULT_POLICY.name}. "
            "Nothing here applies a ruleset: the cutover needs a human with admin."
        )
    else:
        print("\nresult: 0 issues — every baseline satisfies the contract")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, description=__doc__
    )
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument(
        "--repo", action="append", default=[],
        help="limit the run to this repository; repeatable (default: all in the policy)",
    )
    parser.add_argument(
        "--no-live", action="store_true",
        help="skip the committed-versus-live comparison even if a token is present",
    )
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    args = parser.parse_args(argv)

    try:
        policy = load_policy(args.policy)
        repos = args.repo or policy["repos"]
        unknown = [r for r in repos if r not in policy["repos"]]
        if unknown:
            raise ToolError(f"{', '.join(unknown)}: not declared in {args.policy}")
        report = run(policy, repos, want_live=not args.no_live)
    except ToolError as exc:
        print(f"check-ruleset-conformance: {exc}", file=sys.stderr)
        return EXIT_NO_VERDICT

    if args.json:
        print(json.dumps(
            {
                "checked": report.checked,
                "liveChecked": report.live_checked,
                "liveSkippedReason": report.live_skipped_reason,
                "findings": report.findings,
                "notes": report.notes,
                "conforming": report.conforming,
            },
            indent=2,
        ))
    else:
        print_report(report, policy)

    return EXIT_CONFORMING if report.conforming else EXIT_DIVERGED


if __name__ == "__main__":
    sys.exit(main())
