"""
AlgoSentinel Smart Contract — ARC-4 / PyTEAL
Deploys to Algorand Testnet.
Logs DeFi monitoring alerts on-chain with full transparency.

Methods:
  log_alert(severity, title, description)  → stores alert hash on-chain
  update_risk(liquidation, volatility)     → updates risk scores
  get_status()                             → returns agent state
  bootstrap()                             → initialises global state (called once on deploy)
"""

from pyteal import *

# ── GLOBAL STATE SCHEMA ──────────────────────────────────────────────────────
# 8 key-value pairs (within 64 allowed)
GLOBAL_INTS  = 6   # alert_count, last_block, agent_active, txns_scanned, liq_risk, vol_risk
GLOBAL_BYTES = 2   # version, last_alert_hash

# ── APPROVAL PROGRAM ─────────────────────────────────────────────────────────
def approval():

    # ── Selectors (ARC-4 method routing) ─────────────────────────────────────
    is_bootstrap    = Txn.application_args[0] == MethodSignature("bootstrap()void")
    is_log_alert    = Txn.application_args[0] == MethodSignature("log_alert(string,string,string)void")
    is_update_risk  = Txn.application_args[0] == MethodSignature("update_risk(uint64,uint64)void")
    is_get_status   = Txn.application_args[0] == MethodSignature("get_status()string")

    # ── On create ─────────────────────────────────────────────────────────────
    on_create = Seq([
        App.globalPut(Bytes("version"),       Bytes("4.0.0")),
        App.globalPut(Bytes("alert_count"),   Int(0)),
        App.globalPut(Bytes("last_block"),    Global.round()),
        App.globalPut(Bytes("agent_active"),  Int(1)),
        App.globalPut(Bytes("txns_scanned"),  Int(0)),
        App.globalPut(Bytes("liq_risk"),      Int(0)),
        App.globalPut(Bytes("vol_risk"),      Int(0)),
        App.globalPut(Bytes("last_alert"),    Bytes("")),
        Approve(),
    ])

    # ── bootstrap() ──────────────────────────────────────────────────────────
    handle_bootstrap = Seq([
        Assert(Txn.sender() == Global.creator_address()),
        App.globalPut(Bytes("agent_active"), Int(1)),
        App.globalPut(Bytes("last_block"),   Global.round()),
        Log(Bytes("AlgoSentinel bootstrapped")),
        Approve(),
    ])

    # ── log_alert(severity, title, description) ───────────────────────────────
    # ARC-4: args[1]=severity, args[2]=title, args[3]=description
    handle_log_alert = Seq([
        # Increment counter
        App.globalPut(
            Bytes("alert_count"),
            App.globalGet(Bytes("alert_count")) + Int(1)
        ),
        # Store block of last alert
        App.globalPut(Bytes("last_block"), Global.round()),
        # Store a hash of severity+title as proof
        App.globalPut(
            Bytes("last_alert"),
            Concat(Txn.application_args[1], Bytes(":"), Txn.application_args[2])
        ),
        # Increment txns scanned
        App.globalPut(
            Bytes("txns_scanned"),
            App.globalGet(Bytes("txns_scanned")) + Int(1)
        ),
        # Emit log for AVM indexer visibility
        Log(Concat(
            Bytes("ALERT:"),
            Txn.application_args[1],   # severity
            Bytes(":"),
            Txn.application_args[2],   # title
        )),
        Approve(),
    ])

    # ── update_risk(liquidation_score, volatility_score) ─────────────────────
    handle_update_risk = Seq([
        App.globalPut(Bytes("liq_risk"), Btoi(Txn.application_args[1])),
        App.globalPut(Bytes("vol_risk"), Btoi(Txn.application_args[2])),
        App.globalPut(Bytes("last_block"), Global.round()),
        Log(Concat(
            Bytes("RISK:liq="),
            Txn.application_args[1],
            Bytes(",vol="),
            Txn.application_args[2],
        )),
        Approve(),
    ])

    # ── get_status() ──────────────────────────────────────────────────────────
    handle_get_status = Seq([
        Log(Concat(
            Bytes("STATUS:alerts="),
            Itob(App.globalGet(Bytes("alert_count"))),
            Bytes(",block="),
            Itob(App.globalGet(Bytes("last_block"))),
            Bytes(",active="),
            Itob(App.globalGet(Bytes("agent_active"))),
        )),
        Approve(),
    ])

    # ── Delete / Update (only creator) ───────────────────────────────────────
    on_delete = Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Approve(),
    ])

    on_update = Seq([
        Assert(Txn.sender() == Global.creator_address()),
        Approve(),
    ])

    # ── Router ────────────────────────────────────────────────────────────────
    program = Cond(
        [Txn.application_id() == Int(0),             on_create],
        [Txn.on_completion()  == OnComplete.DeleteApplication, on_delete],
        [Txn.on_completion()  == OnComplete.UpdateApplication, on_update],
        [Txn.on_completion()  == OnComplete.NoOp,
            Cond(
                [is_bootstrap,   handle_bootstrap],
                [is_log_alert,   handle_log_alert],
                [is_update_risk, handle_update_risk],
                [is_get_status,  handle_get_status],
            )
        ],
    )

    return program


def clear():
    return Approve()


if __name__ == "__main__":
    import os, json
    from pyteal import compileTeal, Mode

    approval_teal = compileTeal(approval(), mode=Mode.Application, version=8)
    clear_teal    = compileTeal(clear(),    mode=Mode.Application, version=8)

    os.makedirs("build", exist_ok=True)
    with open("build/approval.teal", "w") as f:
        f.write(approval_teal)
    with open("build/clear.teal", "w") as f:
        f.write(clear_teal)

    print("✓ Compiled approval.teal and clear.teal to build/")
    print(f"  Approval: {len(approval_teal.splitlines())} lines")
    print(f"  Clear:    {len(clear_teal.splitlines())} lines")
