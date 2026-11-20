#!/bin/bash
# Verification gate, run inside Docker by `docker-manage.sh test`.
# Runs every suite even after a failure and gives one final verdict, so a
# later success can't mask an earlier failure. Arguments go to Hugo.
set -uo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")/.."

failed=()

echo "==== Hugo: full render, warnings are failures"
hugo --renderToMemory --panicOnWarning \
    --printPathWarnings --printI18nWarnings "$@" || failed+=(hugo)

echo "==== Data generator: unit tests"
python3 -m unittest discover -s scripts/data -p 'test_*.py' || failed+=(data)

# Same style rules as our other Python repositories: black at 79
# columns (also set in pyproject.toml, for editors), and flake8
# configured in .flake8.
echo "==== Python: black"
black --check --line-length 79 scripts || failed+=(black)

echo "==== Python: flake8"
flake8 scripts || failed+=(flake8)

if [ "${#failed[@]}" -ne 0 ]; then
    echo "==== FAILED: ${failed[*]}" >&2
    exit 1
fi
echo "==== All checks passed"
