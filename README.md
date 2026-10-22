# STRIVE: Agentic AI and Smart Contracts for Early-Warning Student Support

Code, smart contracts, data and raw results for the paper *STRIVE: Agentic AI and Smart Contracts for Early-Warning Student Support and Transparent Disbursement of Retention Funds*.

- `code/` – risk-model experiments (`ml_experiments.py`), rule-based agent pipeline (`agent_sim.py`), figure scripts
- `contracts/` – Solidity contracts (InterventionRegistry, SupportFundVault), Hardhat tests and benchmark scripts
- `data/data.csv` – UCI *Predict Students' Dropout and Academic Success* (https://doi.org/10.24432/C5MC89, CC BY 4.0)
- `results/` – raw outputs reported in the paper

Run `./reproduce.sh` (Python 3.10+, Node 18+).
