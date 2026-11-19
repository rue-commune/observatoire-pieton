# Observatoire piéton

A Hugo static site publishing pedestrian-safety observations, starting with
parking within 5 m of pedestrian crossings in Nantes Métropole (LOM law,
deadline 31 December 2026). `observatoire-passages-pietons-nantes.html` is
the original self-contained Leaflet page that the site grows from.

Before any git or gh operation (status, diff, add, commit, branch,
merge, rebase, push, PRs, issues), read and follow [GIT.md](GIT.md).
Before changing deployment, Cloudflare settings, the basemap or the
Hugo version, read and follow [DEPLOY.md](DEPLOY.md).

## Environment

The Hugo toolchain lives in Docker; Hugo is not installed on the host.
Agents run on the host and invoke Docker from there. Before running any
build or test command, check where you are and say so: inside Docker the
working directory is `/devsrc`; on the host it is a deep path such as
`/home/jeff/src/...`.

Jeff's interactive Bash function `dm` runs `docker/docker-manage.sh` from
the `docker/` directory, forwarding all arguments. `dm test` therefore
means `(cd docker && ./docker-manage.sh test)`; use the equivalent
`./docker/docker-manage.sh test` when `dm` isn't available in your shell.

| Command | Effect |
| --- | --- |
| `./docker/docker-manage.sh test` | Verification gate (`scripts/test.sh`): strict Hugo render |
| `./docker/docker-manage.sh build` | `hugo --gc --cleanDestinationDir` into `public/` |
| `./docker/docker-manage.sh serve` | Live server on http://localhost:1313/ (drafts shown) |
| `./docker/docker-manage.sh sh` | Shared interactive shell in the container |
| `./docker/docker-manage.sh down` | Stop the development stack |

`-b` before the action rebuilds the image without cache. Extra arguments
to `build`, `test` and `serve` are appended to the hugo command. The
Hugo version is pinned by `HUGO_VERSION` in `docker/Dockerfile`.

## Testing

- Run `./docker/docker-manage.sh test` before handing off any change, and
  report its real result. You may run it without asking.
- Never commit with a failing test gate.
- If you can't run the tests (no Docker, network failure, etc.), say so
  clearly, explain why, and ask the user to run them. Don't skip
  verification silently.
- Run the gate before every commit, even for changes that look unrelated;
  it is cheap and catches pre-existing breakage.
- For changes to `docker/` shell scripts, also run `bash -n` on them and
  `docker compose -f docker/compose.yml config --quiet`.

## Review before commit

- Any non-trivial change gets an independent review before a commit is
  proposed or work is handed off. Trivial means typo fixes, comment
  tweaks or one-line non-logic edits; treat anything ambiguous as
  non-trivial. Apply the same rigour whatever the code's origin: your
  own work, another session's, or a human's.
- Do a light self-check during implementation to catch obvious mistakes
  early. Do the heavy pass once the change is believed complete: a few
  focused reviewer subagents in parallel (correctness, security,
  compliance with these instructions), or `/code-review`.
- Say when a review starts, that you are waiting on it, what it found and
  how each point was addressed. Count each reviewer launch out loud
  ("launching a second review subagent").
- After substantive fixes, re-review with a fresh subagent. A review
  passes when it comes back clean, with only trivial points, or with
  points deliberately left unaddressed and explained. Past about three
  rounds, suspect a loop or deeper problem and ask the human.
- Judge review feedback, human or agent, on its merits. If you disagree,
  say so and why; don't silently comply or silently ignore it.

Reviews are read-only unless asked to fix. Findings should:

- Exclude pre-existing issues, lines the change didn't touch, things a
  linter or the test gate already catches, deliberately silenced issues,
  and nitpicks a senior engineer wouldn't raise.
- State the triggering condition and the impact ("fails when X because
  Y"), ranked by severity, with `file:line` references, plus a commit
  SHA when the review is posted outside the working tree.
- The project has no CI, so reviewers run the test gate themselves.
- Stay scoped to the diff plus what is needed to verify a suspicion.
- Say explicitly when nothing was found.

## Subagents

Delegate to a subagent when a subtask would flood the main context with
disposable output (wide searches, file dumps, web research) or suits a
different model: cheaper for a narrow, well-specified job, more capable
for something hard. Do small or tightly coupled work inline; spawning has
its own overhead and loses shared context.

## Style and language

- Site content and user-facing text are in French. Code comments, commit
  messages and these instructions use British English.
- No gratuitous whitespace or formatting changes unrelated to the task.
- Comment where it adds value (why, not what).
- Follow formatter/linter configuration when the project adds any, rather
  than personal taste.

## Layout

- `content/_index.md`: the home page; `ville:` selects the city.
- `assets/villes/<ville>/config.json`: hand-maintained city settings and
  texts, inlined verbatim (key order matters to the app; don't
  re-serialise it). `tuiles` is the keyless IGN Plan IGN v2 tile URL.
- `assets/villes/<ville>/data.json`: generated data, replaced on each
  update. Never edit it by hand.
- `assets/css/observatoire.css`, `assets/js/observatoire.js`: the app,
  shared by all cities, inlined into the page.
- `layouts/home.html`: assembles the single self-contained page.
- `scripts/`: project scripts, including `test.sh`, the gate itself.
- `public/` and `resources/_gen/` are generated and ignored. Docker files
  live in `docker/`; the build context is the repository root, so
  `.dockerignore` sits there.

## Basemap and the old CARTO key

Tiles come from IGN's Géoplateforme (Plan IGN v2), which needs no key, so
the site has no secrets. See DEPLOY.md for why, and for what was used
before.

`observatoire-passages-pietons-nantes.html` is the original page. It
embeds a CARTO API key, is git-ignored, and must never be committed.
Never add that key to any file.

## Updating the data

Replace `assets/villes/<ville>/data.json` with the new generated file,
then run the test gate. The layout validates the JSON, the required
keys (present and non-null), the `generated` date, and the absence of
`</script` or `<!--`, so a malformed update fails the build
instead of shipping a broken page. If the pipeline also changed source
dates or texts, update `config.json` too. Commit the data update on its
own.

When you have read this file, say so aloud.
