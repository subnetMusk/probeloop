#!/bin/sh
# The downloaded package needs Docker Desktop and the operating system's standard shell only.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
fail() { printf '\n%s\n' "$1" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || fail 'Install Docker Desktop from https://www.docker.com/products/docker-desktop/, then start this launcher again.'
docker info >/dev/null 2>&1 || fail 'Open Docker Desktop, wait until its engine is running, then start this launcher again.'
docker compose version >/dev/null 2>&1 || fail 'Update Docker Desktop: its Docker Compose plugin is required.'
printf '\nStarting ProbeLoop. The first download can take several minutes.\n'
docker compose up -d || fail 'ProbeLoop could not start. If port 8000 is occupied, set PROBELOOP_PORT=8001 in the .env file beside this launcher and try again. Your saved data has been kept.'
backend_id=$(docker compose ps -q backend)
attempt=0
while [ "$attempt" -lt 300 ]; do
  health=$(docker inspect --format '{{.State.Health.Status}}' "$backend_id")
  [ "$health" = healthy ] && break
  attempt=$((attempt + 1))
  if [ $((attempt % 15)) -eq 0 ]; then printf 'Preparing the application. The first start can take longer on a cold Docker cache.\n'; fi
  sleep 2
done
[ "$health" = healthy ] || fail 'ProbeLoop is taking longer than expected. Open Docker Desktop and inspect the backend service logs, then run this launcher again. Saved data is preserved.'
address=$(docker compose port backend 8000)
url="http://$address"
printf '\nProbeLoop is ready: %s\nKeep Docker Desktop running while you use the app.\n' "$url"
case "$(uname -s)" in
  Darwin) open "$url" ;;
  *) if command -v xdg-open >/dev/null 2>&1; then xdg-open "$url" >/dev/null 2>&1 || true; fi ;;
esac
