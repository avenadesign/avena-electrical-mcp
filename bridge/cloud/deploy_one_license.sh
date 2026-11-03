#!/usr/bin/env bash
# Avena Electrical: one permanent license per mobile, no OAuth identity transfer.
# Root-only, transactional migration. Restores old code/data if deployment fails.
set -Eeuo pipefail
if [[ "$(id -u)" != "0" ]]; then
  echo "Please run as root: sudo bash deploy_one_license.sh" >&2
  exit 1
fi
SITE="https://raw.githubusercontent.com/avenadesign/avena-electrical-mcp"
SRC="$SITE/768c8cda2d6ba382b32100c7332d518063e058a1/bridge/cloud/oauth_core.py"
FRONT="$SITE/52d698834a9d30b7d30da1ed0ea7f238f6f0a7ea/bridge/cloud/oauth_front.py"
MIGRATE="$SITE/624136937b0aa92bc371fbeec68a10637b8d5ebe/bridge/cloud/one_license_migration.py"
CLOUD="/opt/avena-elc/cloud"
DB="/opt/avena-elc/state/oauth.sqlite"
TMP="$(mktemp -d /tmp/avena-license.XXXXXXXX)"
chmod 755 "$TMP"
SERVICES_STOPPED=0
SUCCESS=0
cleanup() {
  status=$?
  if [[ "$SUCCESS" = 0 && "$SERVICES_STOPPED" = 1 ]]; then
    echo "Error: restoring previous login service and database" >&2
    systemctl stop avena-elc-oauth || true
    systemctl stop avena-elc-mcp || true
    cp "$TMP/oauth_core.old.py" "$CLOUD/oauth_core.py" || true
    cp "$TMP/oauth_front.old.py" "$CLOUD/oauth_front.py" || true
    if [[ -s "$TMP/pre.sqlite" ]]; then
      python3 - "$TMP/pre.sqlite" "$DB" <<'PY' || true
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as source:
    with sqlite3.connect(sys.argv[2]) as target:
        source.backup(target)
PY
    fi
  fi
  if [[ "$SERVICES_STOPPED" = 1 ]]; then
    systemctl start avena-elc-mcp || true
    systemctl start avena-elc-oauth || true
  fi
  rm -rf -- "$TMP"
  exit "$status"
}
trap cleanup EXIT
test -r "$DB"
test -r "$CLOUD/oauth_core.py"
test -r "$CLOUD/oauth_front.py"
curl -fsSL "$SRC" -o "$TMP/oauth_core.py"
curl -fsSL "$FRONT" -o "$TMP/oauth_front.py"
curl -fsSL "$MIGRATE" -o "$TMP/one_license_migration.py"
chmod 644 "$TMP"/*.py
python3 -m py_compile "$TMP"/*.py
cp "$CLOUD/oauth_core.py" "$TMP/oauth_core.old.py"
cp "$CLOUD/oauth_front.py" "$TMP/oauth_front.old.py"
echo "Stopping OAuth and MCP for license consolidation"
SERVICES_STOPPED=1
systemctl stop avena-elc-oauth
systemctl stop avena-elc-mcp
python3 - "$DB" "$TMP/pre.sqlite" <<'PY'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as source:
    with sqlite3.connect(sys.argv[2]) as target:
        source.backup(target)
PY
chmod 600 "$TMP/pre.sqlite"
runuser -u avena-elc -- python3 "$TMP/one_license_migration.py" "$DB"
install -m 644 "$TMP/oauth_core.py" "$CLOUD/oauth_core.py"
install -m 644 "$TMP/oauth_front.py" "$CLOUD/oauth_front.py"
systemctl start avena-elc-mcp
systemctl start avena-elc-oauth
systemctl is-active --quiet avena-elc-mcp
systemctl is-active --quiet avena-elc-oauth
python3 - "$DB" <<'PY'
import sqlite3,sys
with sqlite3.connect(sys.argv[1]) as c:
    active=c.execute("SELECT COUNT(*) FROM pairings WHERE revoked=0").fetchone()[0]
    numbers=c.execute("SELECT COUNT(*) FROM phone_licenses").fetchone()[0]
    dup=c.execute("SELECT COUNT(*) FROM (SELECT phone FROM pairings WHERE revoked=0 GROUP BY phone HAVING COUNT(*)>1)").fetchone()[0]
    if active!=numbers or dup:
        raise RuntimeError("License database invariants failed")
    print("Verified one active license per mobile:",active)
PY
SUCCESS=1
echo "ONE_LICENSE_DEPLOYMENT_OK. Existing wrong/duplicate codes are now revoked."
echo "ChatGPT connections using a revoked code must sign in with the retained code."
