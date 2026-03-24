"""
AlgoSentinel — Testnet Deploy & Interact Script
================================================
Deploys the AlgoSentinel smart contract to Algorand Testnet and
provides helper functions used by app.py to call it.

Usage:
  python deploy_contract.py          ← deploy fresh contract
  python deploy_contract.py status   ← read on-chain state
  python deploy_contract.py test     ← run a full test cycle

Requirements:
  pip install py-algorand-sdk pyteal

Testnet faucet (get free ALGO):
  https://bank.testnet.algorand.network/
"""

import os
import sys
import json
import base64
import time
from pathlib import Path

try:
    import algosdk
    from algosdk import account, mnemonic, encoding
    from algosdk.v2client import algod, indexer
    from algosdk.transaction import (
        ApplicationCreateTxn, ApplicationNoOpTxn,
        StateSchema, OnComplete, wait_for_confirmation
    )
    from algosdk.abi import Method, Contract
    ALGOSDK_AVAILABLE = True
except ImportError:
    ALGOSDK_AVAILABLE = False
    print("⚠  py-algorand-sdk not installed. Run: pip install py-algorand-sdk")

# ── TESTNET CONFIG ────────────────────────────────────────────────────────────
TESTNET_NODE    = "https://testnet-api.algonode.cloud"
TESTNET_INDEXER = "https://testnet-idx.algonode.cloud"
APP_ID_FILE     = Path(__file__).parent / "deployed_app_id.json"

# ── ARC-4 ABI (matches the contract exactly) ─────────────────────────────────
ABI_JSON = {
    "name": "AlgoSentinel",
    "desc": "Autonomous DeFi Monitoring Agent — on-chain alert logging",
    "networks": {},
    "methods": [
        {
            "name": "bootstrap",
            "desc": "Initialise contract state (creator only)",
            "args": [],
            "returns": {"type": "void"}
        },
        {
            "name": "log_alert",
            "desc": "Log a DeFi monitoring alert on-chain",
            "args": [
                {"name": "severity",    "type": "string", "desc": "crit|warn|info|opp"},
                {"name": "title",       "type": "string", "desc": "Alert title"},
                {"name": "description", "type": "string", "desc": "Alert detail"},
            ],
            "returns": {"type": "void"}
        },
        {
            "name": "update_risk",
            "desc": "Update on-chain risk scores",
            "args": [
                {"name": "liquidation", "type": "uint64", "desc": "0-100"},
                {"name": "volatility",  "type": "uint64", "desc": "0-100"},
            ],
            "returns": {"type": "void"}
        },
        {
            "name": "get_status",
            "desc": "Read agent status",
            "args": [],
            "returns": {"type": "string"}
        },
    ]
}

# ── HELPER ────────────────────────────────────────────────────────────────────
def get_clients():
    algod_client   = algod.AlgodClient("", TESTNET_NODE,   headers={"X-API-Key": ""})
    indexer_client = indexer.IndexerClient("", TESTNET_INDEXER, headers={"X-API-Key": ""})
    return algod_client, indexer_client


def load_or_create_account():
    """
    Load account from ALGO_MNEMONIC env var, or generate a new throwaway one.
    For hackathon demos: set ALGO_MNEMONIC to your funded testnet account mnemonic.
    """
    m = os.environ.get("ALGO_MNEMONIC", "").strip()
    if m:
        private_key = mnemonic.to_private_key(m)
        address     = account.address_from_private_key(private_key)
        print(f"  Account loaded: {address}")
        return private_key, address

    # Generate fresh account (needs testnet funding)
    private_key, address = account.generate_account()
    m = mnemonic.from_private_key(private_key)
    print(f"\n  ⚠  NEW ACCOUNT GENERATED — NOT FUNDED")
    print(f"  Address:  {address}")
    print(f"  Mnemonic: {m}")
    print(f"\n  Fund this address at: https://bank.testnet.algorand.network/")
    print(f"  Then re-run:  ALGO_MNEMONIC=\"{m}\" python deploy_contract.py\n")
    return private_key, address


def compile_teal(algod_client, teal_source: str) -> bytes:
    """Compile TEAL source via algod compile endpoint."""
    result = algod_client.compile(teal_source)
    return base64.b64decode(result["result"])


def load_teal(filename: str) -> str:
    """Load a .teal file from the build directory."""
    build_path = Path(__file__).parent / "build" / filename
    if not build_path.exists():
        raise FileNotFoundError(
            f"Build file not found: {build_path}\n"
            f"Run:  python contracts/algosentinel_contract.py  first"
        )
    return build_path.read_text()


def save_app_id(app_id: int, address: str):
    data = {"app_id": app_id, "creator": address, "network": "testnet",
            "deployed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())}
    APP_ID_FILE.write_text(json.dumps(data, indent=2))
    print(f"  App ID saved to {APP_ID_FILE}")


def load_app_id() -> dict | None:
    if APP_ID_FILE.exists():
        return json.loads(APP_ID_FILE.read_text())
    return None


# ── DEPLOY ────────────────────────────────────────────────────────────────────
def deploy(algod_client, private_key: str, address: str) -> int:
    print("\n── Deploying AlgoSentinel contract to Algorand Testnet ──")

    # Check balance
    info = algod_client.account_info(address)
    balance_algo = info["amount"] / 1e6
    print(f"  Balance: {balance_algo:.4f} ALGO")
    if balance_algo < 0.5:
        print(f"  ⚠  Insufficient balance. Fund at https://bank.testnet.algorand.network/")
        sys.exit(1)

    # Compile TEAL
    print("  Compiling TEAL...")
    approval_teal = load_teal("approval.teal")
    clear_teal    = load_teal("clear.teal")
    approval_prog = compile_teal(algod_client, approval_teal)
    clear_prog    = compile_teal(algod_client, clear_teal)
    print(f"  Approval: {len(approval_prog)} bytes | Clear: {len(clear_prog)} bytes")

    # Build transaction
    sp = algod_client.suggested_params()
    txn = ApplicationCreateTxn(
        sender      = address,
        sp          = sp,
        on_complete = OnComplete.NoOpOC,
        approval_program  = approval_prog,
        clear_program     = clear_prog,
        global_schema     = StateSchema(num_uints=6, num_byte_slices=2),
        local_schema      = StateSchema(num_uints=0, num_byte_slices=0),
        note              = b"AlgoSentinel v4.0.0 — Agentic AI x Blockchain",
    )

    # Sign and send
    signed = txn.sign(private_key)
    tx_id  = algod_client.send_transaction(signed)
    print(f"  TX submitted: {tx_id}")
    print("  Waiting for confirmation...")

    result = wait_for_confirmation(algod_client, tx_id, wait_rounds=10)
    app_id = result["application-index"]
    print(f"\n  ✓ Contract deployed!")
    print(f"  App ID:    {app_id}")
    print(f"  Explorer:  https://testnet.explorer.perawallet.app/application/{app_id}/")
    save_app_id(app_id, address)
    return app_id


# ── CALL HELPERS ──────────────────────────────────────────────────────────────
def _method_selector(name_and_args: str) -> bytes:
    """Compute 4-byte ARC-4 method selector."""
    import hashlib
    h = hashlib.new("sha512_256")
    h.update(name_and_args.encode())
    return h.digest()[:4]


def call_log_alert(algod_client, private_key: str, address: str,
                   app_id: int, severity: str, title: str, description: str) -> str:
    """Log a DeFi alert on-chain via ARC-4."""
    sp  = algod_client.suggested_params()
    sel = _method_selector("log_alert(string,string,string)void")

    def encode_string(s: str) -> bytes:
        encoded = s.encode("utf-8")
        return len(encoded).to_bytes(2, "big") + encoded

    txn = ApplicationNoOpTxn(
        sender = address,
        sp     = sp,
        index  = app_id,
        app_args = [
            sel,
            encode_string(severity[:32]),
            encode_string(title[:64]),
            encode_string(description[:128]),
        ],
        note = f"AlgoSentinel alert: {title[:30]}".encode(),
    )
    signed = txn.sign(private_key)
    tx_id  = algod_client.send_transaction(signed)
    wait_for_confirmation(algod_client, tx_id, wait_rounds=6)
    return tx_id


def call_update_risk(algod_client, private_key: str, address: str,
                     app_id: int, liquidation: int, volatility: int) -> str:
    """Update risk scores on-chain."""
    sp  = algod_client.suggested_params()
    sel = _method_selector("update_risk(uint64,uint64)void")
    txn = ApplicationNoOpTxn(
        sender   = address,
        sp       = sp,
        index    = app_id,
        app_args = [
            sel,
            liquidation.to_bytes(8, "big"),
            volatility.to_bytes(8, "big"),
        ],
    )
    signed = txn.sign(private_key)
    tx_id  = algod_client.send_transaction(signed)
    wait_for_confirmation(algod_client, tx_id, wait_rounds=6)
    return tx_id


def read_global_state(algod_client, app_id: int) -> dict:
    """Read global state from Algorand Testnet."""
    info  = algod_client.application_info(app_id)
    state = {}
    for kv in info.get("params", {}).get("global-state", []):
        key = base64.b64decode(kv["key"]).decode("utf-8", errors="replace")
        val = kv["value"]
        if val["type"] == 1:
            raw = base64.b64decode(val["bytes"])
            state[key] = raw.decode("utf-8", errors="replace")
        else:
            state[key] = val["uint"]
    return state


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not ALGOSDK_AVAILABLE:
        print("Install SDK first: pip install py-algorand-sdk pyteal")
        sys.exit(1)

    algod_client, _ = get_clients()
    private_key, address = load_or_create_account()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "deploy"

    if cmd == "deploy":
        app_id = deploy(algod_client, private_key, address)

    elif cmd == "status":
        saved = load_app_id()
        if not saved:
            print("No deployed contract found. Run: python deploy_contract.py")
            sys.exit(1)
        app_id = saved["app_id"]
        print(f"\nReading state for App ID {app_id}...")
        state = read_global_state(algod_client, app_id)
        print(json.dumps(state, indent=2))

    elif cmd == "test":
        saved = load_app_id()
        if not saved:
            print("Deploy first: python deploy_contract.py")
            sys.exit(1)
        app_id = saved["app_id"]
        print(f"\nRunning test cycle on App ID {app_id}...")

        print("  Calling log_alert...")
        tx = call_log_alert(algod_client, private_key, address, app_id,
                            "crit", "Test Alert", "AlgoSentinel test from deploy script")
        print(f"  TX: {tx}")

        print("  Calling update_risk...")
        tx = call_update_risk(algod_client, private_key, address, app_id, 42, 28)
        print(f"  TX: {tx}")

        print("\n  Final state:")
        state = read_global_state(algod_client, app_id)
        print(json.dumps(state, indent=2))
        print("\n  ✓ All tests passed!")

    else:
        print(f"Unknown command: {cmd}. Use: deploy | status | test")
