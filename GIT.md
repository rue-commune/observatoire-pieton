# Git and GitHub

## Working directory

Never `cd` into another worktree or clone to run git, and never chain
`cd <dir> && git ...`: it can silently act on the wrong branch. Use
`git -C <dir> ...` instead. This holds even when no other worktrees
exist yet.

## Committing

- Ask before committing, unless the user asked for work that includes
  committing (e.g. "do X, then commit"). Agent commits go through the
  same review path as anyone else's.
- `git add --intent-to-add` new files as soon as they are created, so
  `git status` and `git diff` show them to you and to reviewers.
- Run the test gate (see CLAUDE.md) and complete the review before
  committing. Never commit with failing tests.
- One logical change per commit; don't bundle unrelated refactors,
  formatting and behaviour changes.

## Destructive operations and pushing

- Force-pushes, `reset --hard`, history rewrites and amending shared
  commits need explicit user involvement every time.
- Never `git push` in any form, including to your own branch, unless the
  prompt explicitly asks. After a history rewrite that push is a
  force-push, which needs fresh approval each time; approval for one
  push doesn't carry over. An authorised force-push is always
  `git push --force-with-lease`, never `--force`/`-f`.

## Git versus GitHub

Git is local; GitHub is a remote service. Anything touching GitHub
(`gh`, PRs, issues, comments) needs specific authorisation, in the prompt
or through a question you ask. Prefer local operations: for a requested
merge, `git merge --ff-only` rather than `gh pr merge`.

## Commit messages

- Subject: imperative present tense, about 50 characters, no trailing
  full stop. Blank line, then a body wrapped at 72 columns (except
  tables, code, URLs and stack traces).
- The body explains why: motivation, approach, alternatives considered,
  trade-offs, operational impact. Not what the diff already shows.
- Bullets use `*`, indented two spaces, with a hanging indent. No blank
  lines between bullets if all are single-line; if any wraps, a blank
  line between every bullet in that list.
- Pass multi-line messages with a heredoc or `-F`, never literal `\n`
  inside `-m`.
- Check subject length and body wrap on the draft before committing,
  not afterwards with `--amend`.
- If the branch name contains a number, it is probably an issue number:
  reference it at the end (`Part of #123`). Sanity-check it against the
  repository's history and issue numbers; ask if it seems implausible.
- Issue references go at the end in a consistent form.
- No emojis. AI co-authorship, if credited, is one plain
  `Co-Authored-By:` line.
- British spelling.

When you have read this file, say so aloud.
