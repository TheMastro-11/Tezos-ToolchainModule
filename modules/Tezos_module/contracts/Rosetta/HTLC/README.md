# HTLC

## Specification

The Hash Timed Locked Contract (HTLC) involves two users, the *committer* and the *receiver*.

At contract creation, the committer:
- deposits a collateral in native cryptocurrency in the contract
- specifies a deadline for the secret revelation, in terms of a delay from publication, in terms of a delay from the publication of the contract
- specifies the receiver of the collateral in case the secret is not revealed within the deadline;
- commits to a value, that is the Keccak-256 digest of a secret bitstring chosen by the committer.

After contract creation, the contract supports two actions:
- **reveal**: allows the committer to redeem the whole contract balance by providing a preimage of the committed hash
- **timeout**: can be called only after the deadline and transfers the whole contract balance to the timeout recipient

## Required functionalities

- Native tokens
- Time constraints
- Transaction revert
- Hash on arbitrary messages

## SmartPy implementation

The SmartPy contract stores `owner`, `verifier`, `hash`, and `reveal_timeout`.
`reveal(secret)` checks the sender and verifies `sp.keccak(sp.pack(secret))` against the stored commitment.
`timeout()` unlocks the contract once the block-level deadline has passed.

## Differences with Solidity/Ethereum

- Commitment verification uses `sp.pack` + `sp.keccak`, which is the SmartPy idiom corresponding to Solidity hashing helpers.
- `reveal` checks that the contract already has positive balance, instead of checking during origination as done in Solidity.
