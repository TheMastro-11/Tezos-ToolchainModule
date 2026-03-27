# Payment Splitter

## Specification

This contract allows to split native cryptocurrency payments among a group of users. The split can be in equal parts or in any other arbitrary proportion, by assigning each account a number of shares.

At deployment, the contract creator specifies the set of users who will receive the payments and the corresponding number of shares. The set of shareholders and their shares cannot be updated thereafter.

After creation, the contract supports the following actions:
- **receive**: allows anyone to deposit cryptocurrency units in the contract;
- **release**: allows anyone to distribute the contract balance to the shareholders through a pull-payment model.

## Required functionalities

- Native tokens
- Transaction revert
- Key-value maps
- Bounded loops

## SmartPy implementation

There are two SmartPy versions:
- `PaymentSplitterRosetta.py`, which mirrors the Solidity structure with explicit payees, shares, released amounts, and helper views;
- `PaymentSplitterRosettaV2.py`, a cleaner variant based on a single `map[address, nat]` of shares.

## Differences with Solidity/Ethereum

- The SmartPy version reconstructs the payee/share association with explicit loops during initialization, whereas Solidity can iterate over constructor arrays more directly.
- Read APIs such as `payee`, `shares`, `released`, and `releasable` are modeled as **off-chain views**.
- The folder includes a second SmartPy implementation (`V2`) that is simpler and closer to the mathematical formulation of the splitter than the first port.
