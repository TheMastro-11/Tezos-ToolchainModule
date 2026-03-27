# Constant-product AMM

## Specification

Tiny AMM (Automated Market Maker) allows users to deposit, redeem, and swap a pair of fungible tokens in a decentralized manner.

The constructor takes two token addresses, `t0` and `t1`.

After creation, the contract is meant to support the following actions:
- **deposit**: transfers `t0` and `t1` from the sender to the AMM while preserving the pool ratio after the first deposit;
- **redeem**: burns liquidity owned by the sender and returns the proportional token amounts;
- **swap**: exchanges one token of the pair for the other, subject to a minimum output constraint.

## Required functionalities

- Custom tokens
- Revert transactions
- Rational arithmetics / arbitrary-precision arithmetics

## SmartPy implementation

The SmartPy contract is written against a token interface exposed through external contract calls (`transfer` and `balance_of`).
Pool reserves are stored as `r0` and `r1`, liquidity supply is stored in `supply`, and each provider balance is tracked in `minted`.
The implementation contains helper routines for token transfers and for post-operation balance verification through callback entrypoints.

## Differences with Solidity/Ethereum

- The SmartPy version relies on **contract-to-contract calls** to token contracts and explicit callback entrypoints to check balances; in Solidity, ERC-20 calls are synchronous from the contract perspective.
- Liquidity ownership is tracked in a `big_map` instead of a Solidity mapping.
- The design is Tezos-oriented: token transfers are built as explicit payloads and sent to external contracts through `sp.transfer`.
- The current SmartPy file is **not feature-complete**: `swap` is unfinished and `redeem` contains typographical issues (`self.data.r1` / `self.data.supply` are misspelled in the file). This should be considered a notable divergence from the coherent Solidity reference implementation.
