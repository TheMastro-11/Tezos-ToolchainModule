# Vesting

## Specification

The contract handles the maturation (vesting) of native cryptocurrency for a given beneficiary.

The contract is initialized by setting:
- the beneficiary address,
- the first block level (`start`) where the beneficiary can withdraw funds,
- the overall duration of the vesting scheme.

After creation, the contract supports the following action:
- **release**: allows the beneficiary to withdraw part of the vested amount according to a linear vesting policy:
  - before the start block, the amount is zero;
  - at any moment between the start and the expiration of the vesting scheme, the amount is proportional to the time passed since the start of the scheme; 
  - once the scheme is expired, the amount is the entire contract balance. 

## Required functionalities

- Native tokens
- Time constraints
- Transaction revert

## SmartPy implementation

The SmartPy contract stores `beneficiary`, `start`, `duration`, and the cumulative amount already `released`.
`release()` computes the vested amount from the current block level, subtracts the amount already released, transfers the delta to the beneficiary, and emits the released amount.
In the scenario, the initial vested funds are provided as the initial contract balance.

## Differences with Solidity/Ethereum

- The SmartPy version keeps track of the cumulative released amount as a `nat` and converts between `nat` and `mutez` explicitly.
- The contract emits the released amount with `sp.emit`, which is a SmartPy-specific way to expose execution information.
