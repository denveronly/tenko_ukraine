#!/bin/sh
# Blocks a commit if staged changes contain something that looks like a token.
PATTERN='eyJ[A-Za-z0-9_-]{20,}\.eyJ|Bearer [A-Za-z0-9._-]{20,}'
if git diff --cached -U0 | grep '^+' | grep -Eq "$PATTERN"; then
  echo "✋ Staged changes look like they contain a token/password. Commit cancelled." >&2
  git diff --cached -U0 | grep '^+' | grep -En "$PATTERN" | cut -c1-80 >&2
  exit 1
fi
