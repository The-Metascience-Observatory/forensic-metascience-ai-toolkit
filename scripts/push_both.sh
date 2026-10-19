#!/bin/sh
# Push main to both GitHub repositories.
#
#   full-history  The-Metascience-Observatory/forensic-metascience-ai-toolkit-full-history
#                 every commit, pushed as is (fast-forward only).
#   origin        The-Metascience-Observatory/forensic-metascience-ai-toolkit
#                 the public repo: ONE commit per push, holding main's exact
#                 tree, on top of the public repo's own previous commit. Its
#                 history is not ours, so a plain `git push origin main` is
#                 always refused, and forcing it would replace the public
#                 history with the full one. Never do either.
#
# The public commit reuses the message of the newest non-merge "Release ..."
# commit on main, or HEAD's message when no release is newer than the last
# public push. Nothing is pushed publicly when the tree is unchanged.
#
# Usage: scripts/push_both.sh        (or `git push-both`)
set -eu

branch=$(git rev-parse --abbrev-ref HEAD)
[ "$branch" = main ] || { echo "push_both: on '$branch', not main" >&2; exit 1; }
git diff --quiet HEAD -- || echo "push_both: note: uncommitted changes are not pushed" >&2

git push full-history main

git fetch -q origin main
public=$(git rev-parse origin/main)
tree=$(git rev-parse 'HEAD^{tree}')
if [ "$(git rev-parse "$public^{tree}")" = "$tree" ]; then
    echo "push_both: public repo already has this tree ($public)"
    exit 0
fi

release=$(git log -1 --no-merges --format=%H --grep='^Release ' HEAD)
if [ -n "$release" ] && [ "$(git log -1 --format=%s "$release")" != \
     "$(git log -1 --format=%s "$public")" ]; then
    msg=$(git log -1 --format=%B "$release")
else
    msg=$(git log -1 --format=%B HEAD)
fi

commit=$(printf '%s\n' "$msg" | git commit-tree "$tree" -p "$public")
git push origin "$commit:refs/heads/main"
git fetch -q origin main
echo "push_both: public main is now $commit"
