#!/usr/bin/env python3
"""SignalBoard bridge: post trading signals to the on-chain board via gnokey.

Reads a JSON list of signals and posts each one with
`gnokey maketx call ... PostSignal` against the Onyx testnet.

Signal JSON format (list of objects):
    {"asset": "BTC/USDT", "direction": "long",
     "refPrice": "67250.50", "note": "Breakout above resistance"}

Usage:
    python3 post_signals.py signals.json            # post from file
    python3 post_signals.py --live                  # build 3 signals from
                                                    # live public prices
    python3 post_signals.py signals.json --dry-run  # print commands only

Environment:
    GNO_REMOTE       gnokey remote URL. Default http://127.0.0.1:26657,
                     which is the local RPC forwarder used on machines
                     whose direct egress is intercepted (see README).
                     On an unrestricted network use
                     https://rpc.onyx.testnets.gno.land:443
    GNO_KEY_NAME     gnokey key name. Default: signalboard
    GNO_KEYPASS_FILE File containing the key password.
                     Default: ~/.keys-gno/keypass.txt

Results (tx hash per signal) are written to last_run.json next to this
script and printed to stdout. Requires the `gnokey` binary on PATH.
"""

import json
import os
import re
import subprocess
import sys
import urllib.request

PKG_PATH = "gno.land/r/g18hk5n6qmgtxqlljy5athr3u3xg669sqayrfv5z/signalboard"
CHAIN_ID = "onyx-1"
REMOTE = os.environ.get("GNO_REMOTE", "http://127.0.0.1:26657")
KEY_NAME = os.environ.get("GNO_KEY_NAME", "signalboard")
KEYPASS_FILE = os.environ.get(
    "GNO_KEYPASS_FILE", os.path.expanduser("~/.keys-gno/keypass.txt")
)
HERE = os.path.dirname(os.path.abspath(__file__))

HASH_RE = re.compile(r"\b([0-9A-F]{64})\b")


def live_signals():
    """Build 3 example signals from live public market data.

    Uses Binance's public data domain (data-api.binance.vision), no key
    required. Direction is a naive 24h-momentum call; these are demo
    signals for the board, not investment advice.
    """
    out = []
    for symbol, asset in [("BTCUSDT", "BTC/USDT"), ("ETHUSDT", "ETH/USDT"),
                          ("SOLUSDT", "SOL/USDT")]:
        url = f"https://data-api.binance.vision/api/v3/ticker/24hr?symbol={symbol}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            t = json.load(resp)
        price = float(t["lastPrice"])
        change = float(t["priceChangePercent"])
        direction = "long" if change >= 0 else "short"
        note = f"24h momentum {change:+.2f}% (bridge example signal)"
        out.append({
            "asset": asset,
            "direction": direction,
            "refPrice": f"{price:.2f}",
            "note": note,
        })
    return out


def post_signal(sig, password, dry_run=False):
    cmd = [
        "gnokey", "maketx", "call",
        "-pkgpath", PKG_PATH,
        "-func", "PostSignal",
        "-args", sig["asset"],
        "-args", sig["direction"],
        "-args", str(sig["refPrice"]),
        "-args", sig.get("note", ""),
        "-gas-fee", "10000ugnot",
        "-gas-wanted", "6000000",
        "-chainid", CHAIN_ID,
        "-remote", REMOTE,
        "-insecure-password-stdin",
        "-broadcast",
        KEY_NAME,
    ]
    if dry_run:
        print("[dry-run]", " ".join(cmd))
        return {"signal": sig, "txHash": None, "dryRun": True}
    env = dict(os.environ)
    local_bin = os.path.expanduser("~/.local/bin")
    if local_bin not in env.get("PATH", ""):
        env["PATH"] = local_bin + ":" + env.get("PATH", "")
    proc = subprocess.run(
        cmd, input=password + "\n", capture_output=True, text=True,
        timeout=300, env=env,
    )
    output = proc.stdout + proc.stderr
    m = HASH_RE.search(output)
    return {
        "signal": sig,
        "txHash": m.group(1) if m else None,
        "returnCode": proc.returncode,
        "outputTail": output.strip().splitlines()[-5:],
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    if "--live" in sys.argv:
        signals = live_signals()
    elif args:
        with open(args[0]) as f:
            signals = json.load(f)
    else:
        print(__doc__)
        return 1

    password = ""
    if not dry_run:
        with open(KEYPASS_FILE) as f:
            password = f.read().strip()

    results = []
    for sig in signals:
        print(f"posting {sig['asset']} {sig['direction']} @ {sig['refPrice']} ...")
        res = post_signal(sig, password, dry_run=dry_run)
        print("  tx:", res.get("txHash"))
        results.append(res)

    out_path = os.path.join(HERE, "last_run.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print("results written to", out_path)
    ok = all(r.get("txHash") or dry_run for r in results)
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
