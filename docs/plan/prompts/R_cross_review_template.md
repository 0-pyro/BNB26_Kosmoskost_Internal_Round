# R: Cross-Review Template
Run in: a fresh Antigravity agent session. Model: Claude Sonnet or Gemini 3.8 Flash.
Settings: Planning mode. Time-box: ~30 mins.

## 1. Mission
You are a peer reviewer. Your job is to review the code in branch `[TARGET_BRANCH]` against the authoritative contracts in `contracts/`.

## 2. Ownership
Read-only access to the repository.

## 3. Build steps
1. `git fetch origin && git checkout origin/[TARGET_BRANCH]`
2. Read `docs/plan/02_contracts.md`.
3. Read the code in `[TARGET_DIRECTORY]`.
4. Check 1: Does the code use the exact JSON schemas and Binary Header formats defined in the contract?
5. Check 2: Are there any hardcoded assumptions that violate the contracts?
6. Check 3: Do the tests pass? Run the tests described in the branch's `INTEGRATION.md`.
7. Output a Markdown report with Pass/Fail and specific line numbers for violations.
