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

echo "==== Unit tests (node --test)"
node --test 'tests/*.test.mjs' || failed+=(unit)

if [ "${#failed[@]}" -ne 0 ]; then
    echo "==== FAILED: ${failed[*]}" >&2
    exit 1
fi
echo "==== All checks passed"
