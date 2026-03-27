# Auction

## Specification

The contract allows a seller to create an English auction, with bids in the native cryptocurrency.

The seller creates the contract by specifying:
- the starting bid of the auction;
- the object of the auction (a string, used for notarization purposes only);
- the seller address.

After creation, the contract supports the following actions:
- **start**: allows the seller to start the auction and set its duration.
- **bid**: allows any user to bid native cryptocurrency after the auction has started and before its duration has expired. If the the amount of the bid is greater than the current highest bid, then it is transferred to the contract; otherwise, the transaction fails.
- **withdraw**: allows any user, at any time, to withdraw their bid if this is not the currently highest one.
- **end**: allows the seller to end the auction after its duration has expired and to withdraw the highest bid.

## Required functionalities

- Native tokens
- Time constraints
- Transaction revert
- Key-value maps

## SmartPy implementation

The SmartPy contract models the auction lifecycle with a `variant` state machine: `WAIT_START`, `WAIT_CLOSING`, and `CLOSED`.
Bids are tracked in a `big_map[address, mutez]`, while `highest_bidder`, `highest_bid`, and `end_time` are stored explicitly.
The seller starts the auction through `start(duration)`, bidders place their offer through `bid()`, and the seller finalizes through `end()`.

## Differences with Solidity/Ethereum

- Time is handled with `sp.now` and `sp.timestamp` arithmetic (`sp.add_seconds`) rather than Solidity block-time primitives.
- The SmartPy implementation uses a `variant` for the auction state instead of a Solidity enum.
- When an already-outbid user bids again, the contract internally triggers its own `withdraw` entrypoint; this is a Tezos/SmartPy-specific way to reuse logic.
