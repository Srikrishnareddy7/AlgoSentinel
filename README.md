# AlgoSentinel v5.0 — Autonomous DeFi Monitoring Agent
### Algorand Hackathon · Agentic AI x Blockchain

> Full-stack AI agent monitoring Algorand DeFi in real-time — real blockchain events,
> real smart contract on Testnet, real Pera Wallet integration.

---

## Project Structure

```
algosentinel/
├── app.py                              ← Flask backend v5 (all fixes applied)
├── templates/
│   └── index.html                      ← Dashboard UI (Pera Wallet + backend connected)
├── contracts/
│   ├── algosentinel_contract.py        ← PyTEAL ARC-4 smart contract
│   └── deploy_contract.py             ← Testnet deploy + interact script
├── requirements.txt
├── render.yaml                         ← Render.com deploy config
└── README.md
```

---

## What Was Fixed (v4 → v5)

| # | Problem | Fix |
|---|---|---|
| 1 | Fake wallet (random address) | Real Pera Wallet SDK + Algorand Indexer balance fetch |
| 2 | No real DeFi event tracking | Polls Indexer for live app calls on Tinyman/Pact/AlgoFi/Humble |
| 3 | No real smart contract | PyTEAL ARC-4 contract + Testnet deploy + live TX logging |

---

## Run Locally

### Step 1 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 2 — Compile the smart contract

```bash
cd contracts
python algosentinel_contract.py
cd ..
```

This generates `contracts/build/approval.teal` and `contracts/build/clear.teal`.

### Step 3 — Start the server (basic — no real contract)

```bash
python app.py
```

Open **http://localhost:5000** — dashboard with real Algorand block data and DeFi event tracking.

---

## Enable Real Smart Contract (Optional but Recommended for Judges)

### Step 1 — Get a funded Testnet account

Option A — Generate a new account:
```bash
cd contracts
python deploy_contract.py
# It will print a new address — copy it
```

Option B — Use an existing Algorand wallet, switch to Testnet.

Fund the address at: **https://bank.testnet.algorand.network/**
(Enter the address, get 10 free ALGO instantly)

### Step 2 — Set your mnemonic

```bash
export ALGO_MNEMONIC="word1 word2 word3 ... word25"
```

### Step 3 — Deploy the contract

```bash
cd contracts
python deploy_contract.py
```

Output:
```
── Deploying AlgoSentinel contract to Algorand Testnet ──
  Balance: 10.0000 ALGO
  Compiling TEAL...
  TX submitted: ABC123XYZ...
  Waiting for confirmation...

  ✓ Contract deployed!
  App ID:    1234567890
  Explorer:  https://testnet.explorer.perawallet.app/application/1234567890/
```

### Step 4 — Run with real contract

```bash
ALGO_MNEMONIC="your 25 words" python app.py
```

Now:
- Critical alerts are automatically written to Algorand Testnet ✓
- Risk scores are updated on-chain every ~5 minutes ✓
- Every on-chain TX is logged in the dashboard ✓

### Step 5 — Test the contract

```bash
cd contracts
ALGO_MNEMONIC="your 25 words" python deploy_contract.py test
```

---

## Enable Real Pera Wallet

The dashboard UI loads the Pera Wallet SDK from CDN automatically.

On the live app, click **CONNECT WALLET**:
- If Pera Wallet browser extension is installed → it opens Pera connect
- Otherwise → prompts for manual Algorand address entry
- Either way → fetches real balance from Algorand Mainnet Indexer

---

## Deploy to Render.com (Public URL for Judges)

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "AlgoSentinel v5.0 — Algorand DeFi Agent"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/algosentinel.git
git push -u origin main
```

### Step 2 — Deploy on Render

1. Go to **https://render.com** → New Web Service
2. Connect your GitHub repo
3. Render reads `render.yaml` automatically
4. In Environment Variables, add: `ALGO_MNEMONIC` = your 25-word mnemonic
5. Click **Deploy**

Your live URL: `https://algosentinel.onrender.com`

---

## Hackathon Requirements Checklist

| Requirement | Status | Implementation |
|---|---|---|
| AI-based DeFi monitoring | ✅ Full | Background agent with risk scoring, anomaly detection, AI analysis |
| Real-time blockchain event tracking | ✅ Full | Algorand Indexer polls Tinyman/Pact/AlgoFi/Humble app calls every 30s |
| Liquidation / anomaly detection | ✅ Full | LTV threshold alerts, whale detection on real txns, wash-trading signals |
| Automated alert system | ✅ Full | SSE push pipeline: backend → EventSource → dashboard in real-time |
| Dashboard (portfolio, risk, trends) | ✅ Full | Full 5-tab dashboard with charts, gauges, terminal, transaction feed |
| Wallet integration | ✅ Full | Pera Wallet SDK + manual address + real Indexer balance fetch |
| Transparent on-chain logging | ✅ Full | PyTEAL ARC-4 contract on Algorand Testnet logs every critical alert |

---

## Smart Contract ABI (ARC-4)

```json
{
  "name": "AlgoSentinel",
  "methods": [
    { "name": "bootstrap",    "args": [],                                              "returns": "void" },
    { "name": "log_alert",    "args": ["severity:string","title:string","desc:string"], "returns": "void" },
    { "name": "update_risk",  "args": ["liquidation:uint64","volatility:uint64"],       "returns": "void" },
    { "name": "get_status",   "args": [],                                               "returns": "string" }
  ]
}
```

Global state keys: `alert_count`, `last_block`, `agent_active`, `txns_scanned`, `liq_risk`, `vol_risk`, `version`, `last_alert`

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Block, price, risk, agent state |
| `/api/events` | GET | **NEW** Real DeFi app calls from Algorand Mainnet |
| `/api/transactions` | GET | Recent Algorand transactions (real) |
| `/api/alerts` | GET/POST | Alert feed |
| `/api/wallet/connect` | POST | Connect wallet (real address validation) |
| `/api/contract/deploy` | POST | Deploy PyTEAL contract to Testnet |
| `/api/contract/state` | GET | Read on-chain global state |
| `/api/contract/call` | POST | Call ARC-4 method |
| `/api/stream` | GET | SSE real-time event stream |
| `/api/agent/analyze` | POST | Trigger AI analysis cycle |
