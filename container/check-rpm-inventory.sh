#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

baseline=$1
inventory=$2

rpm -qa --qf '%{NAME}|%{EPOCHNUM}:%{VERSION}-%{RELEASE}|%{ARCH}|%{LICENSE}\n' > "$inventory"
sort -o "$inventory" "$inventory"
differences=$(cut -d '|' -f1,3- "$inventory" | sort | comm -3 "$baseline" -)
if [[ -n "$differences" ]]; then
    printf 'RPM package or license differs from the reviewed baseline (expected left, installed right):\n%s\n' \
        "$differences" >&2
    exit 1
fi
