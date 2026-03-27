# Vault

## Specification

Vaults are a security mechanism to prevent cryptocurrency from being immediately withdrawn by an adversary who has stolen the owner's private key.

To create the vault, the owner specifies:
- a recovery key, which can be used to cancel a withdrawal request;
- a wait time, which must elapse between a withdrawal request and the actual transfer.

Once the vault contract has been created, it supports the following actions:
- **receive**: allows anyone to deposit native cryptocurrency in the contract;
- **withdraw**: allows the owner to issue a withdrawal request, specifying the receiver and the desired amount;
- **finalize**: allows the owner to finalize the withdrawal after the wait time has passed;
- **cancel**: allows the recovery key holder to cancel the pending withdrawal during the waiting period.

## Required functionalities

- Native tokens
- Time constraints
- Transaction revert

## SmartPy implementation

The SmartPy contract stores `owner`, `recovery`, `wait_time`, the optional pending `receiver`, the optional `request_time`, the requested `amount`, and a two-state `variant` (`IDLE` / `REQ`).
`withdraw()` starts a pending request, `finalize()` executes it after enough blocks have elapsed, and `cancel()` clears it.

## Differences with Solidity/Ethereum

- State is represented with a SmartPy `variant` instead of a Solidity enum.
