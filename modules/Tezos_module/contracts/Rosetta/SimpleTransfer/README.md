# Simple transfer

## Specification

The contract allows a user (the *owner*) to deposit native cryptocurrency, and another user (the *recipient*) to withdraw arbitrary fractions of the contract balance.

At contract creation, the owner specifies the recipient's address.

After contract creation, the contract supports two actions:
- **deposit**: allows the owner to deposit an arbitrary positive amount of native cryptocurrency in the contract;
- **withdraw**: allows the recipient to withdraw any amount not exceeding the contract balance.

## Required functionalities

- Native tokens
- Transaction revert

## SmartPy implementation

The contract stores only `owner` and `recipient`.
`deposit()` checks that the caller is the owner and that a positive amount was sent, while `withdraw(amount)` can be called only by the recipient and transfers tez with `sp.send`.

## Differences with Solidity/Ethereum

- nothing
