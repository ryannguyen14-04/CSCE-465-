#!/bin/bash
set -euo pipefail

if [[ $# -ne 1 || "$1" != "course-marker" ]]; then
    printf 'Usage: safe_marker.sh course-marker\n' >&2
    exit 1
fi

marker_dir="/home/ubuntu/csce465-agentsec/hw1/markers"

if [[ ! -d "$marker_dir" || -L "$marker_dir" ]]; then
    printf 'Error: markers must be an existing real directory.\n' >&2
    exit 1
fi

umask 077
set -o noclobber
printf 'course-marker\n' > "$marker_dir/marker.txt"
printf 'Created marker.txt\n'
