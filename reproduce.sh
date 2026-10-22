#!/usr/bin/env bash
# Reproduce all STRIVE results and figures.
set -euo pipefail
cd "$(dirname "$0")"
pip install -r requirements.txt
python code/ml_experiments.py   | tee results/ml_log.txt
python code/agent_sim.py
python code/fig1_arch.py; python code/fig2_sequence.py; python code/fig_results.py
cd contracts && npm ci && npx hardhat test | tee ../results/security_tests.txt
npx hardhat run scripts/*.js || true
