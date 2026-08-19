#!/usr/bin/env python3
"""Regression tests for tools/check-ruleset-conformance.py's pure functions.

Run with:
    python3 -m unittest discover -s tools/tests -t tools/tests

Nothing here touches the network. The GitHub reads are the thin part; the part
worth pinning is the judgement — what counts as conforming, what an exception
excuses, and when an exception has stopped describing reality.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "check_ruleset_conformance", TOOLS_DIR / "check-ruleset-conformance.py"
)
conformance = importlib.util.module_from_spec(_spec)
sys.modules["check_ruleset_conformance"] = conformance
_spec.loader.exec_module(conformance)


REQUIREMENTS = {
    "min_required_approving_review_count": 1,
    "strict_required_status_checks_policy": False,
    "required_rule_types": [
        "pull_request",
        "deletion",
        "non_fast_forward",
        "required_linear_history",
        "required_status_checks",
    ],
    "required_status_check_contexts": ["scan / scan", "signatures / signatures"],
}


def policy(exceptions=None, repos=("apps", "platform")):
    return {
        "owner": "jdwlabs",
        "repos": list(repos),
        "baseline": {
            "path": ".github/rulesets/baseline.json",
            "ruleset_name": "Baseline",
            "ref": "refs/heads/main",
        },
        "requirements": REQUIREMENTS,
        "exceptions": list(exceptions or []),
    }


def baseline(approvals=1, strict=False, contexts=None, rule_types=None, enforcement="active",
             refs=("refs/heads/main",), code_owner=False):
    contexts = ["scan / scan", "signatures / signatures"] if contexts is None else contexts
    rule_types = REQUIREMENTS["required_rule_types"] if rule_types is None else rule_types
    rules = []
    for rule_type in rule_types:
        if rule_type == "pull_request":
            rules.append({
                "type": "pull_request",
                "parameters": {
                    "required_approving_review_count": approvals,
                    "require_code_owner_review": code_owner,
                },
            })
        elif rule_type == "required_status_checks":
            rules.append({
                "type": "required_status_checks",
                "parameters": {
                    "strict_required_status_checks_policy": strict,
                    "required_status_checks": [{"context": c} for c in contexts],
                },
            })
        else:
            rules.append({"type": rule_type})
    return {
        "name": "Baseline",
        "enforcement": enforcement,
        "conditions": {"ref_name": {"include": list(refs), "exclude": []}},
        "rules": rules,
        "bypass_actors": [],
    }


class CheckDocumentTests(unittest.TestCase):
    def check(self, document, pol=None, repo="apps"):
        consumed = set()
        findings = conformance.check_document(repo, document, pol or policy(), consumed)
        return findings, consumed

    def test_a_conforming_baseline_produces_nothing(self):
        findings, _ = self.check(baseline())
        self.assertEqual(findings, [])

    def test_extra_required_contexts_are_conforming(self):
        # The whole reason per-repo rulesets exist: platform requires 12 of its
        # own contexts and must not be told to trim them to the org's floor.
        findings, _ = self.check(
            baseline(contexts=["scan / scan", "signatures / signatures", "go-lint", "yamllint"])
        )
        self.assertEqual(findings, [])

    def test_a_missing_org_wide_context_is_a_finding(self):
        findings, _ = self.check(baseline(contexts=["scan / scan"]))
        self.assertEqual(len(findings), 1)
        self.assertIn("signatures / signatures", findings[0])

    def test_too_few_approvals_is_a_finding(self):
        findings, _ = self.check(baseline(approvals=0))
        self.assertEqual(len(findings), 1)
        self.assertIn("requires 0 approving review(s)", findings[0])

    def test_a_code_owner_requirement_counts_as_one_approval(self):
        findings, _ = self.check(baseline(approvals=0, code_owner=True))
        self.assertEqual(findings, [])

    def test_strict_mismatch_is_a_finding(self):
        findings, _ = self.check(baseline(strict=True))
        self.assertEqual(len(findings), 1)
        self.assertIn("strict_required_status_checks_policy=true", findings[0])

    def test_a_missing_rule_type_is_a_finding(self):
        findings, _ = self.check(baseline(rule_types=["pull_request", "required_status_checks"]))
        self.assertEqual(
            sorted(f.split("missing the ")[1] for f in findings),
            ["'deletion' rule", "'non_fast_forward' rule", "'required_linear_history' rule"],
        )

    def test_a_disabled_ruleset_is_a_finding(self):
        findings, _ = self.check(baseline(enforcement="disabled"))
        self.assertTrue(any("not 'active'" in f for f in findings))

    def test_a_ruleset_that_does_not_cover_main_is_a_finding(self):
        findings, _ = self.check(baseline(refs=["refs/heads/release/**"]))
        self.assertTrue(any("does not cover refs/heads/main" in f for f in findings))

    def test_default_branch_wildcard_counts_as_covering_main(self):
        findings, _ = self.check(baseline(refs=["~DEFAULT_BRANCH"]))
        self.assertEqual(findings, [])


class ExceptionTests(unittest.TestCase):
    REASON = "A recorded decision with enough words in it to read as an actual reason."

    def test_a_matching_exception_clears_the_finding_and_is_consumed(self):
        pol = policy([{
            "repo": "deployments",
            "requirement": "min_required_approving_review_count",
            "observed": 0,
            "reason": self.REASON,
        }])
        consumed = set()
        findings = conformance.check_document("deployments", baseline(approvals=0), pol, consumed)
        self.assertEqual(findings, [])
        self.assertIn(("deployments", "min_required_approving_review_count"), consumed)

    def test_an_exception_for_another_repo_does_not_apply(self):
        pol = policy([{
            "repo": "deployments",
            "requirement": "min_required_approving_review_count",
            "observed": 0,
            "reason": self.REASON,
        }])
        findings = conformance.check_document("apps", baseline(approvals=0), pol, set())
        self.assertEqual(len(findings), 1)

    def test_an_exception_excusing_a_different_value_is_a_finding(self):
        # The value moved. An exception written for 0 must not keep excusing
        # whatever the number becomes.
        pol = policy([{
            "repo": "apps",
            "requirement": "strict_required_status_checks_policy",
            "observed": False,
            "reason": self.REASON,
        }])
        findings = conformance.check_document("apps", baseline(strict=True), pol, set())
        self.assertEqual(len(findings), 1)
        self.assertIn("no longer describes it", findings[0])


class LoadPolicyTests(unittest.TestCase):
    def write(self, document):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        json.dump(document, handle)
        handle.close()
        return Path(handle.name)

    def test_a_valid_policy_loads(self):
        self.assertEqual(conformance.load_policy(self.write(policy()))["owner"], "jdwlabs")

    def test_a_missing_file_is_no_verdict(self):
        with self.assertRaises(conformance.ToolError):
            conformance.load_policy(Path("/nonexistent/org-policy.json"))

    def test_an_exception_without_a_reason_is_rejected(self):
        document = policy([{
            "repo": "apps",
            "requirement": "strict_required_status_checks_policy",
            "observed": True,
            "reason": "known issue",
        }])
        with self.assertRaisesRegex(conformance.ToolError, "no usable reason"):
            conformance.load_policy(self.write(document))

    def test_an_exception_missing_observed_is_rejected(self):
        document = policy([{
            "repo": "apps",
            "requirement": "strict_required_status_checks_policy",
            "reason": "A long enough reason to pass the word count check here.",
        }])
        with self.assertRaisesRegex(conformance.ToolError, "observed"):
            conformance.load_policy(self.write(document))

    def test_the_shipped_policy_is_valid(self):
        conformance.load_policy(conformance.DEFAULT_POLICY)


class SummaryDifferenceTests(unittest.TestCase):
    def test_identical_documents_differ_in_nothing(self):
        self.assertEqual(conformance.summary_differences(baseline(), baseline()), [])

    def test_a_context_present_only_in_the_committed_file_is_reported(self):
        # platform's live case: the JSON on main requires a context the ruleset
        # in force does not, because nobody ran apply.sh after the merge.
        committed = baseline(contexts=["scan / scan", "signatures / signatures", "adr-numbering"])
        live = baseline(contexts=["scan / scan", "signatures / signatures"])
        differences = conformance.summary_differences(committed, live)
        self.assertEqual(differences, ["contexts: committed-only: adr-numbering"])

    def test_a_scalar_difference_names_both_sides(self):
        differences = conformance.summary_differences(baseline(approvals=1), baseline(approvals=0))
        self.assertEqual(differences, ["approvals: committed=1 live=0"])


class UnappliedRulesetTests(unittest.TestCase):
    """A committed ruleset with no live counterpart of the same name.

    platform's `change-class-review-gate.json` is in exactly this state: merged,
    never applied, protecting nothing, and invisible from the repository alone.
    """

    def setUp(self):
        self.original = conformance.committed_ruleset_names
        self.addCleanup(setattr, conformance, "committed_ruleset_names", self.original)

    def stub(self, names):
        conformance.committed_ruleset_names = lambda *_args, **_kwargs: names

    def test_a_committed_ruleset_with_no_live_counterpart_is_reported(self):
        self.stub({"Baseline": "baseline.json", "Change Class Review Gate": "ccrg.json"})
        live = [{"name": "Baseline"}]
        self.assertEqual(
            conformance.unapplied_rulesets("jdwlabs", "platform", ".github/rulesets", live),
            ["ccrg.json ('Change Class Review Gate')"],
        )

    def test_every_committed_ruleset_being_live_reports_nothing(self):
        self.stub({"Baseline": "baseline.json"})
        live = [{"name": "Baseline"}, {"name": "Release Tag Protection"}]
        self.assertEqual(
            conformance.unapplied_rulesets("jdwlabs", "platform", ".github/rulesets", live), []
        )

    def test_a_live_ruleset_with_no_committed_file_is_not_reported(self):
        # Out of scope on purpose: this check is about files that were merged
        # and never applied, not about rules created outside the repository.
        self.stub({"Baseline": "baseline.json"})
        live = [{"name": "Baseline"}, {"name": "Created In The UI"}]
        self.assertEqual(
            conformance.unapplied_rulesets("jdwlabs", "platform", ".github/rulesets", live), []
        )


if __name__ == "__main__":
    unittest.main()
