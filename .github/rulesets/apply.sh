#!/usr/bin/env bash
# Applies ruleset exports to GitHub. Requires gh (authenticated with admin on
# the target repository) and jq.
#
# Rulesets are managed as code: edit the JSON, merge via PR, then run this
# script. Applying is a separate, manual, post-merge step — merging the JSON
# changes nothing on its own.
#
#   ./apply.sh                                   # this checkout's repo, from this directory
#   ./apply.sh --dry-run                         # print what would change, write nothing
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
# Re-export after any out-of-band UI change with:
#   gh api repos/<owner>/<repo>/rulesets/<id> | jq . > <name>.json
#
# jq emits CRLF on Windows; pipe through `tr -d '\r'` when re-exporting there,
# or the whole file reads as changed on the next diff.

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
POLICY="$DIR/org-policy.json"

DRY_RUN=no
FORCE=no
ALL=no
WORKSPACE=""
APPLY_DIR=""
REPOS=()

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

# Applies every export in $2 to repository $1. Returns the number of files
# processed on stdout's last line via the global `processed`.
processed=0
apply_dir_to_repo() {
  local repo=$1 dir=$2
  [ -d "$dir" ] || die "$dir: not a directory"

  local found=no file
  for file in "$dir"/*.json; do
    [ -e "$file" ] || continue

    # A ruleset export always carries `target`; anything else in this directory
    # (org-policy.json above all) is configuration, not a ruleset to apply.
    local target
    target=$(jq -r '.target // empty' "$file")
    if [ -z "$target" ]; then
      continue
    fi
    found=yes

    local name id source
    name=$(jq -r '.name' "$file")
    id=$(jq -r '.id // empty' "$file")
    source=$(jq -r '.source // empty' "$file")

    # Refusing rather than skipping: a broadcast that silently dropped the
    # exports it should not have applied would report a clean run over a
    # repository it never touched.
    if [ -n "$source" ] && [ "$source" != "$repo" ] && [ "$FORCE" = no ]; then
      die "${file##*/} was exported from $source, not $repo. Applying it here would overwrite that repository's own rules with another's — including required status checks naming CI jobs that do not exist here. Point --dir at $repo's own rulesets directory, or pass --force if replacing them is the intent."
    fi

    # Read-only fields the API rejects or ignores on write.
    local payload
    payload=$(jq 'del(.id, .node_id, .source, .source_type, .created_at, .updated_at, .current_user_can_bypass, ._links)' "$file")

    local method endpoint match
    if [ -n "$id" ] && gh api "repos/$repo/rulesets/$id" >/dev/null 2>&1; then
      method=PUT; endpoint="repos/$repo/rulesets/$id"; match="id $id"
    else
      local live_id
      live_id=$(gh api "repos/$repo/rulesets" 2>/dev/null \
        | jq -r --arg n "$name" 'map(select(.name == $n and .source_type == "Repository")) | .[0].id // empty') || live_id=""
      if [ -n "$live_id" ]; then
        method=PUT; endpoint="repos/$repo/rulesets/$live_id"; match="name \"$name\" (id $live_id)"
      else
        method=POST; endpoint="repos/$repo/rulesets"; match="no match — creating"
      fi
    fi

    if [ "$DRY_RUN" = yes ]; then
      echo "would $method $endpoint  ($name from ${file##*/}; matched by $match)"
    else
      printf '%s' "$payload" | gh api -X "$method" "$endpoint" --input - >/dev/null
      echo "$method $endpoint  ($name from ${file##*/}; matched by $match)"
    fi
    processed=$((processed + 1))
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
    checkout="$WORKSPACE/$short"
    rulesets="$checkout/.github/rulesets"
    if [ ! -d "$rulesets" ]; then
      die "$rulesets: not found. --all applies each repository's own exports, so every repository in $POLICY needs a checkout under $WORKSPACE."
    fi
    echo "== $owner/$short  ($rulesets)"
    apply_dir_to_repo "$owner/$short" "$rulesets"
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
    echo "== $repo  ($APPLY_DIR)"
    apply_dir_to_repo "$repo" "$APPLY_DIR"
  done
fi

if [ "$DRY_RUN" = yes ]; then
  echo "dry run: $processed ruleset file(s) would be applied — nothing was written"
else
  echo "done: $processed ruleset file(s) applied"
fi
