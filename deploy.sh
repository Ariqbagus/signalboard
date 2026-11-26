#!/usr/bin/env bash
# Deploy SignalBoard to the Onyx testnet (chain onyx-1) and wait until
# the realm is live (new packages pass the gpao approval queue, so the
# render query can fail with "package not known" for a while).
#
# Prerequisites:
#   - gnokey on PATH, key "signalboard" created and FUNDED from
#     https://onyx.testnets.gno.land/faucet (hCaptcha in a browser)
#   - key password in ~/.keys-gno/keypass.txt
#   - GNO_REMOTE: gnokey remote URL. Default http://127.0.0.1:26657
#     (local forwarder for networks with intercepted direct egress).
#     On an unrestricted network:
#     GNO_REMOTE=https://rpc.onyx.testnets.gno.land:443 ./deploy.sh
set -euo pipefail

export PATH="$HOME/.local/bin:$PATH"
ADDR="g18hk5n6qmgtxqlljy5athr3u3xg669sqayrfv5z"
PKG_PATH="gno.land/r/${ADDR}/signalboard"
REMOTE="${GNO_REMOTE:-http://127.0.0.1:26657}"
KEY_NAME="${GNO_KEY_NAME:-signalboard}"
PW="$(cat ~/.keys-gno/keypass.txt)"
cd "$(dirname "$0")"

echo "== balance of $ADDR"
gnokey query bank/balances/"$ADDR" -remote "$REMOTE"

echo "== addpkg $PKG_PATH"
printf '%s\n' "$PW" | gnokey maketx addpkg \
  -pkgpath "$PKG_PATH" \
  -pkgdir . \
  -gas-fee 30000ugnot \
  -gas-wanted 25000000 \
  -max-deposit 100000000ugnot \
  -chainid onyx-1 \
  -remote "$REMOTE" \
  -insecure-password-stdin \
  -broadcast \
  "$KEY_NAME" | tee /tmp/signalboard-addpkg.out
grep -oE '\b[0-9A-F]{64}\b' /tmp/signalboard-addpkg.out | head -1 \
  > /tmp/signalboard-addpkg.hash || true
echo "addpkg tx hash: $(cat /tmp/signalboard-addpkg.hash)"

echo "== waiting for the realm to become active (gpao queue)..."
for i in $(seq 1 60); do
  if gnokey query vm/qrender -remote "$REMOTE" \
      -data "${PKG_PATH}:" 2>/dev/null | grep -q 'SignalBoard'; then
    echo "realm is LIVE after ~$((i * 10))s"
    echo "gnoweb: https://onyx.testnets.gno.land/r/${ADDR}/signalboard"
    exit 0
  fi
  sleep 10
done
echo "realm not active yet after 10 minutes; gpao approval may still be"
echo "pending. Check status/reason on the gpas testnet explorer and rerun"
echo "the render query later:"
echo "  gnokey query vm/qrender -remote $REMOTE -data '${PKG_PATH}:'"
exit 1
