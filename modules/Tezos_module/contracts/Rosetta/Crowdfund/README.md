# Crowdfund

## Specification

The Crowdfund contract allows users to donate native cryptocurrency to fund a campaign.
To create the contract, one must specify:
- the *recipient* of the funds
- the *goal* of the campaign, that is the least amount of currency that
must be donated in order for the campaign to be succesfull
- the *deadline* for the donations

After creation, the following actions are possible:
- **donate**: anyone can transfer native cryptocurrency to the contract until the deadline;
- **withdraw**: after the deadline, the recipient can withdraw the funds stored in the contract, provided that the goal has been reached;
- **reclaim**: after the deadline, if the goal has not been reached donors can withdraw the amounts they have donated.

## Required functionalities

- Native tokens
- Time constraints
- Transaction revert
- Key-value maps

## SmartPy implementation

The SmartPy contract stores donations in a `big_map[address, mutez]` named `donors`.
`donate()` accumulates the transferred amount for `sp.sender`, `withdraw()` releases the full balance to the receiver once the goal is met, and `reclaim()` lets each donor pull back their own contribution after an unsuccessful campaign.
The deadline is represented as a block level (`end_donate`).

## Differences with Solidity/Ethereum

- Contributions are accumulated directly in a Tezos `big_map` and reclaimed with a pull-payment pattern.
- In practice, the SmartPy scenario initializes donor entries before donation; this reflects the stricter access style of the current implementation compared with a more permissive Solidity mapping update.
