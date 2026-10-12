#!/usr/bin/env bash
set -e
interval="${PULLIO_INTERVAL_SECONDS:-21600}"
if [[ ! "$interval" =~ ^[0-9]+$ ]] || (( interval < 60 )); then
    echo 'PULLIO_INTERVAL_SECONDS must be an integer of at least 60' >&2
    exit 1
fi
if [[ ! -f compose.yaml ]]; then
    echo 'compose.yaml not visible at the original host working directory' >&2
    exit 1
fi
trap 'exit 0' TERM INT
while true; do
    echo "$(date -u +%FT%TZ): Checking tagged ArtCraft worker images with Pullio"
    # The artcraft tag restricts this instance to our labels, avoiding other stacks.
    # Upstream Pullio also prunes unused/dangling Docker images at the end of a run.
    /usr/local/bin/pullio --tag artcraft || echo 'Pullio check failed; retrying at next interval' >&2
    sleep "$interval" &
    wait $! || true
done
