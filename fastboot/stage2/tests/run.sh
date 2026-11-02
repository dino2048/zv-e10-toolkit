#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
task_tmp=$(mktemp -d "${TMPDIR:-/tmp}/stage2-tests.XXXXXX")
trap 'rm -rf "$task_tmp"' EXIT
for unit in partition sdhci; do
    clang -std=gnu11 -O1 -fsanitize=undefined -fno-sanitize-recover=all \
      -DHAVE_FETCH=1 -DDL_BUF_ADDR=host_dl_buf \
      -include tests/host_io.h -Itests -Iinclude "tests/${unit}_test.c" tests/optlog_stubs.c -o "$task_tmp/$unit"
    "$task_tmp/$unit"
done
for mode in HAVE_FLASH; do
    clang -std=gnu11 -O1 -fsanitize=undefined -fno-sanitize-recover=all \
      -D"$mode"=1 -DHAVE_FETCH=1 -DDL_BUF_ADDR=host_dl_buf \
      -include tests/host_io.h -Itests -Iinclude \
      tests/fb_test.c tests/optlog_stubs.c -o "$task_tmp/$mode"
    "$task_tmp/$mode"
done
clang -std=gnu11 -O1 -fsanitize=undefined -fno-sanitize-recover=all \
  -DHAVE_FLASH=1 -DHAVE_FETCH=1 -DDL_BUF_ADDR=host_dl_buf \
  -include tests/host_io.h -Itests -Iinclude \
  tests/sparse_test.c tests/optlog_stubs.c -o "$task_tmp/sparse"
"$task_tmp/sparse"
${PYTHON:-python3} -B tests/test_bootstrap.py
${PYTHON:-python3} -B tests/test_release.py
${PYTHON:-python3} -B tests/test_recovery.py
