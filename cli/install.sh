#!/bin/sh
# Install the speaker CLI

set -eu

INSTALL_DIR="${INSTALL_DIR:-/usr/local/bin}"
CONFIG_DIR="${CONFIG_DIR:-$HOME/.speaker}"
BASE_URL="${BASE_URL:-https://raw.githubusercontent.com/speakerdata/speaker/main/cli}"
SKILL_URL="${SKILL_URL:-https://raw.githubusercontent.com/speakerdata/speaker/main/SKILL.md}"

fail() {
  echo "Error: $1" >&2
  exit 1
}

cleanup() {
  [ -n "${TMP_SPEAKER:-}" ] && rm -f "$TMP_SPEAKER"
  [ -n "${TMP_DOCS:-}" ] && rm -f "$TMP_DOCS"
}

download() {
  url="$1"
  out="$2"

  if ! curl --fail --show-error --silent --location \
    --retry 3 --retry-delay 1 --connect-timeout 10 --max-time 60 \
    "$url" -o "$out"; then
    fail "Failed to download: $url"
  fi

  [ -s "$out" ] || fail "Downloaded file is empty: $url"
}

command -v curl >/dev/null 2>&1 || fail "curl is required"
command -v mktemp >/dev/null 2>&1 || fail "mktemp is required"

[ -d "$INSTALL_DIR" ] || mkdir -p "$INSTALL_DIR" || fail "Install directory does not exist and could not be created: $INSTALL_DIR"
[ -w "$INSTALL_DIR" ] || fail "No write access to $INSTALL_DIR (use sudo or set INSTALL_DIR)"

TMP_SPEAKER="$(mktemp)"
TMP_DOCS="$(mktemp)"
trap cleanup EXIT INT TERM HUP

echo "Installing speaker CLI..."

download "$BASE_URL/speaker" "$TMP_SPEAKER"
download "$SKILL_URL" "$TMP_DOCS"

mkdir -p "$CONFIG_DIR"

cp "$TMP_SPEAKER" "$INSTALL_DIR/speaker"
chmod 755 "$INSTALL_DIR/speaker"

cp "$TMP_DOCS" "$CONFIG_DIR/SKILL.md"
chmod 644 "$CONFIG_DIR/SKILL.md"

echo ""
echo "  ✓ speaker installed to $INSTALL_DIR/speaker"
echo "  ✓ Agent docs saved to $CONFIG_DIR/SKILL.md"
echo ""
echo "  Get started:"
echo "    speaker signup          Create an account"
echo "    speaker help            See all commands"
echo ""
