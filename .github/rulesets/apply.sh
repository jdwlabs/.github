#!/usr/bin/env bash
# Applies ruleset exports to GitHub. Requires gh (authenticated with admin on
# the target repository) and jq.
#
# Rulesets are managed as code: edit the JSON, merge via PR, then run this
# script. Applying is a separate, manual, post-merge step — merging the JSON
# changes nothing on its own.
#
#   ./apply.sh --dry-run                         # diff every export against live
#   ./apply.sh                                   # this checkout's repo, from this directory
#   ./apply.sh --repo jdwlabs/platform \
#              --dir ../../../platform/.github/rulesets
#   ./apply.sh --all --workspace ~/projects/jdwlabs
#
# Read docs/rulesets.md before renaming a required check. Changing a job name
# needs a three-step sequence across this script and a pull request, and the
# window between steps is one in which those checks are not enforced.
#
# The target repository defaults to whatever `origin` points at, so a copy of
# this script is correct wherever it is checked out. It used to be a hardcoded
# string, which meant each repository needed its own copy; `--repo` and `--dir`
# replace that, and one copy can now drive every repository.
#
# Every repository's exports are its own. Required status checks name that
# repository's CI jobs, and the four repositories legitimately require between
# 4 and 13 different contexts — so broadcasting one repository's `baseline.json`
# to another would delete the contexts it does not know about. Each export
# records the repository it came from in its `source` field, and applying a file
# to any other repository is refused unless `--force` says otherwise. `--all`
# walks a workspace of checkouts and applies each repository's *own* directory,
# never this one's.
#
# Matching, in order: the `id` embedded in the export if that id still exists on
# the target (PUT), else a ruleset on the target with the same `name` (PUT),
# else create (POST). Name matching is what makes an apply to a repository whose
# ids this file does not carry idempotent — without it, a second "Baseline"
# would be created alongside the existing one.
#
# The whole run is planned before anything is written: every file is parsed,
# every target resolved and every export diffed against the ruleset in force,
# and any refusal aborts before the first write. A run that stopped halfway
# would leave some repositories reconciled and others not, which is the state
# hardest to notice and hardest to undo. Exports already identical to live are
# reported and skipped rather than rewritten.
#
# A change that removes a required status check, lowers the approval count,
# drops a rule or stops enforcing is refused unless `--allow-weakening` says it
# is deliberate. Step 1 of the rename sequence in docs/rulesets.md is exactly
# such a change, so that flag is part of the documented procedure rather than an
# escape hatch — it exists to make the weakening a thing someone typed.
#
# Re-export after any out-of-band UI change with:
#   gh api repos/<owner>/<repo>/rulesets/<id> | jq . > <name>.json
#
# jq emits CRLF on Windows; pipe through `tr -d '\r'` when re-exporting there,
# or the whole file reads as changed on the next diff.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY="$DIR/org-policy.json"

# Fields GitHub returns but rejects or ignores on write. Stripping them from
# both sides is what makes a live-versus-committed diff mean something: without
# it every export differs by its own timestamps.
STRIP_READONLY='del(.id, .node_id, .source, .source_type, .created_at, .updated_at, .current_user_can_bypass, ._links)'

DRY_RUN=no
FORCE=no
ALL=no
ALLOW_WEAKENING=no
WORKSPACE=""
APPLY_DIR=""
REPOS=()

WORK=""
cleanup() { [ -z "$WORK" ] || rm -rf "$WORK"; }
trap cleanup EXIT

die() {
  echo "apply.sh: $*" >&2
  exit 2
}

usage() {
  sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# The repository `origin` points at, so the default target follows the checkout
# rather than a string that has to be edited per copy.
repo_from_origin() {
  local url
  url=$(git -C "$DIR" remote get-url origin 2>/dev/null) || return 1
  printf '%s\n' "$url" | sed -E 's#^.*github\.com[:/]##; s#\.git$##'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=yes ;;
    --force) FORCE=yes ;;
    --all) ALL=yes ;;
    --allow-weakening) ALLOW_WEAKENING=yes ;;
    --repo)
      [ $# -ge 2 ] || die "--repo needs an <owner>/<repo> argument"
      REPOS+=("$2"); shift ;;
    --dir)
      [ $# -ge 2 ] || die "--dir needs a directory argument"
      APPLY_DIR="$2"; shift ;;
    --workspace)
      [ $# -ge 2 ] || die "--workspace needs a directory argument"
      WORKSPACE="$2"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
  shift
done

command -v gh >/dev/null 2>&1 || die "gh is not installed"
command -v jq >/dev/null 2>&1 || die "jq is not installed"

WORK=$(mktemp -d)

# The plan, one entry per export, built in full before anything is written.
PLAN_REPO=()
PLAN_FILE=()
PLAN_NAME=()
PLAN_METHOD=()
PLAN_ENDPOINT=()
PLAN_MATCH=()
PLAN_VERDICT=()   # create | change | unchanged
PLAN_DIFF=()      # path to the unified diff, empty for create/unchanged
PLAN_WEAKENS=()   # newline-separated reasons, empty when nothing is weakened

# Protections the committed export drops relative to what is live. Anything
# listed here makes the branch easier to push to after the apply than before.
# shellcheck disable=SC2016  # a jq program: $live and $new are jq bindings
weakening_filter='
  def contexts: [.rules[]? | select(.type == "required_status_checks")
                 | .parameters.required_status_checks[]? | .context];
  def approvals: [.rules[]? | select(.type == "pull_request")
                  | .parameters.required_approving_review_count // 0] | max;
  def types: [.rules[]?.type];
  . as $new
  | $live
  | [
      (((.  | contexts) - ($new | contexts))[] | "no longer requires the check: \(.)"),
      (((.  | types)    - ($new | types))[]    | "no longer has the rule: \(.)"),
      (if (.  | approvals) != null and ($new | approvals) != null
          and ($new | approvals) < (. | approvals)
       then "lowers required approvals from \(. | approvals) to \($new | approvals)"
       else empty end),
      (if .enforcement == "active" and $new.enforcement != "active"
       then "stops enforcing: active -> \($new.enforcement)"
       else empty end)
    ][]
'

plan_dir_for_repo() {
  local repo=$1 dir=$2
  [ -d "$dir" ] || die "$dir: not a directory"

  local found=no file
  for file in "$dir"/*.json; do
    [ -e "$file" ] || continue

    jq -e . "$file" >/dev/null 2>&1 || die "${file}: not valid JSON"

    # A ruleset export always carries `target`; anything else in this directory
    # (org-policy.json above all) is configuration, not a ruleset to apply.
    local target
    target=$(jq -r '.target // empty' "$file")
    if [ -z "$target" ]; then
      continue
    fi
    found=yes

    local name id source
    name=$(jq -r '.name // empty' "$file")
    id=$(jq -r '.id // empty' "$file")
    source=$(jq -r '.source // empty' "$file")
    [ -n "$name" ] || die "${file}: has a \"target\" but no \"name\" — it cannot be matched against anything live"

    # Refusing rather than skipping: a broadcast that silently dropped the
    # exports it should not have applied would report a clean run over a
    # repository it never touched.
    if [ -n "$source" ] && [ "$source" != "$repo" ] && [ "$FORCE" = no ]; then
      die "${file##*/} was exported from $source, not $repo. Applying it here would overwrite that repository's own rules with another's — including required status checks naming CI jobs that do not exist here. Point --dir at $repo's own rulesets directory, or pass --force if replacing them is the intent."
    fi

    local slot=${#PLAN_REPO[@]}
    local live="$WORK/live.$slot.json"
    local method endpoint match verdict="" diff="" weakens=""

    if [ -n "$id" ] && gh api "repos/$repo/rulesets/$id" >"$live" 2>/dev/null; then
      method=PUT; endpoint="repos/$repo/rulesets/$id"; match="id $id"
    else
      local live_id
      live_id=$(gh api "repos/$repo/rulesets" 2>/dev/null \
        | jq -r --arg n "$name" 'map(select(.name == $n and .source_type == "Repository")) | .[0].id // empty') || live_id=""
      if [ -n "$live_id" ] && gh api "repos/$repo/rulesets/$live_id" >"$live" 2>/dev/null; then
        method=PUT; endpoint="repos/$repo/rulesets/$live_id"; match="name \"$name\" (id $live_id)"
      else
        method=POST; endpoint="repos/$repo/rulesets"; match="no live ruleset named \"$name\""
        rm -f "$live"
      fi
    fi

    if [ "$method" = POST ]; then
      verdict=create
    else
      diff="$WORK/diff.$slot.txt"
      if diff -u \
        --label "live   $endpoint" <(jq -S "$STRIP_READONLY" "$live") \
        --label "commit ${file##*/}" <(jq -S "$STRIP_READONLY" "$file") \
        >"$diff"; then
        verdict=unchanged
        diff=""
      else
        verdict=change
        weakens=$(jq -r --slurpfile l <(jq "$STRIP_READONLY" "$live") \
          '$l[0] as $live | '"$weakening_filter" "$file")
      fi
    fi

    PLAN_REPO+=("$repo")
    PLAN_FILE+=("$file")
    PLAN_NAME+=("$name")
    PLAN_METHOD+=("$method")
    PLAN_ENDPOINT+=("$endpoint")
    PLAN_MATCH+=("$match")
    PLAN_VERDICT+=("$verdict")
    PLAN_DIFF+=("$diff")
    PLAN_WEAKENS+=("$weakens")
  done

  # An empty directory is not a clean run. Nothing was applied and the caller
  # would otherwise read the exit code as everything being in place.
  [ "$found" = yes ] || die "$dir contains no ruleset exports (no *.json with a \"target\" field)"
}

if [ "$ALL" = yes ]; then
  [ ${#REPOS[@]} -eq 0 ] || die "--all and --repo are mutually exclusive"
  [ -z "$APPLY_DIR" ] || die "--all and --dir are mutually exclusive: --all resolves each repository's own directory"
  [ -n "$WORKSPACE" ] || die "--all needs --workspace <dir>, the parent directory holding a checkout of each repository"
  [ -f "$POLICY" ] || die "$POLICY: not found — --all reads the repository list from it"

  owner=$(jq -r '.owner' "$POLICY")
  mapfile -t names < <(jq -r '.repos[]' "$POLICY")
  [ ${#names[@]} -gt 0 ] || die "$POLICY declares no repositories"

  for short in "${names[@]}"; do
    rulesets="$WORKSPACE/$short/.github/rulesets"
    if [ ! -d "$rulesets" ]; then
      die "$rulesets: not found. --all applies each repository's own exports, so every repository in $POLICY needs a checkout under $WORKSPACE."
    fi
    plan_dir_for_repo "$owner/$short" "$rulesets"
  done
else
  if [ ${#REPOS[@]} -eq 0 ]; then
    default_repo=$(repo_from_origin) \
      || die "cannot read the origin remote of $DIR — pass --repo <owner>/<repo>"
    [ -n "$default_repo" ] || die "origin remote of $DIR is not a github.com URL — pass --repo <owner>/<repo>"
    REPOS=("$default_repo")
  fi
  [ -n "$APPLY_DIR" ] || APPLY_DIR="$DIR"

  for repo in "${REPOS[@]}"; do
    plan_dir_for_repo "$repo" "$APPLY_DIR"
  done
fi

[ ${#PLAN_REPO[@]} -gt 0 ] || die "nothing to do: no ruleset exports were found"

# Every weakening in one message. Reporting them one at a time would have the
# operator re-run to discover the next.
weakening_report=""
for i in "${!PLAN_REPO[@]}"; do
  [ -n "${PLAN_WEAKENS[$i]}" ] || continue
  weakening_report+="  ${PLAN_REPO[$i]}  ${PLAN_FILE[$i]##*/}"$'\n'
  while IFS= read -r reason; do
    [ -n "$reason" ] || continue
    weakening_report+="      $reason"$'\n'
  done <<<"${PLAN_WEAKENS[$i]}"
done

if [ -n "$weakening_report" ] && [ "$ALLOW_WEAKENING" = no ] && [ "$DRY_RUN" = no ]; then
  die "this run would weaken branch protection and nothing was written:
$weakening_report
Re-run with --dry-run to read the full diff. If the weakening is the intent —
step 1 of the rename sequence in docs/rulesets.md is exactly this — re-run with
--allow-weakening."
fi

# One block per repository, so a per-repository result is never folded into an
# aggregate count that hides which repository failed.
changes=0
creates=0
unchanged=0
failed=()
current=""

for i in "${!PLAN_REPO[@]}"; do
  if [ "${PLAN_REPO[$i]}" != "$current" ]; then
    current="${PLAN_REPO[$i]}"
    printf '\n== %s\n' "$current"
  fi

  file=${PLAN_FILE[$i]##*/}
  case "${PLAN_VERDICT[$i]}" in
    unchanged)
      unchanged=$((unchanged + 1))
      printf '   %-10s %-32s %s\n' unchanged "$file" "${PLAN_NAME[$i]}"
      continue ;;
    create)
      creates=$((creates + 1))
      printf '   %-10s %-32s %s\n' create "$file" "${PLAN_NAME[$i]}"
      printf '              %s %s — %s\n' "${PLAN_METHOD[$i]}" "${PLAN_ENDPOINT[$i]}" "${PLAN_MATCH[$i]}" ;;
    change)
      changes=$((changes + 1))
      printf '   %-10s %-32s %s\n' change "$file" "${PLAN_NAME[$i]}"
      printf '              %s %s — matched by %s\n' "${PLAN_METHOD[$i]}" "${PLAN_ENDPOINT[$i]}" "${PLAN_MATCH[$i]}"
      sed 's/^/              /' "${PLAN_DIFF[$i]}"
      if [ -n "${PLAN_WEAKENS[$i]}" ]; then
        while IFS= read -r reason; do
          [ -n "$reason" ] || continue
          printf '              !! %s\n' "$reason"
        done <<<"${PLAN_WEAKENS[$i]}"
      fi ;;
  esac

done

if [ "$DRY_RUN" = no ]; then
  printf '\n-- applying\n'
  for i in "${!PLAN_REPO[@]}"; do
    [ "${PLAN_VERDICT[$i]}" != unchanged ] || continue
    payload=$(jq "$STRIP_READONLY" "${PLAN_FILE[$i]}")
    if printf '%s' "$payload" | gh api -X "${PLAN_METHOD[$i]}" "${PLAN_ENDPOINT[$i]}" --input - >/dev/null; then
      printf '   ok    %s  %s (%s)\n' "${PLAN_REPO[$i]}" "${PLAN_FILE[$i]##*/}" "${PLAN_METHOD[$i]}"
    else
      printf '   FAIL  %s  %s (%s)\n' "${PLAN_REPO[$i]}" "${PLAN_FILE[$i]##*/}" "${PLAN_METHOD[$i]}"
      failed+=("${PLAN_REPO[$i]} ${PLAN_FILE[$i]##*/}")
    fi
  done
fi

printf '\n'
if [ "$DRY_RUN" = yes ]; then
  echo "dry run over ${#PLAN_REPO[@]} export(s): $changes would change, $creates would be created, $unchanged already match — nothing was written"
  [ -z "$weakening_report" ] || printf 'applying this would weaken branch protection and needs --allow-weakening:\n%s' "$weakening_report"
  exit 0
fi

echo "applied: $changes changed, $creates created, $unchanged left alone"
if [ ${#failed[@]} -gt 0 ]; then
  printf 'FAILED on %d export(s) — the run is half-applied and these repositories are not reconciled:\n' "${#failed[@]}"
  printf '  %s\n' "${failed[@]}"
  exit 1
fi
