# Escrow

## Specification

The escrow contract acts as a trusted intermediary between a buyer and a seller, aiming to protect the buyer from the possible non-delivery of the purchased goods.

The contract is initialized by setting:
- the buyer's address;
- the seller's address;
- the amount of native cryptocurrency required as a payment.

Immediately after the initialization, the contract supports a single action:
- **deposit**, which allows the buyer to deposit the required amount in the contract.

Once the deposit action has been performed, exactly one of the following actions is possible:
- **pay**, which allows the buyer to transfer the whole escrowed amount to the seller.
- **refund**, which allows the seller to transfer the whole escrowed amount back to the buyer.

## Required functionalities

- Native tokens
- Transaction revert

## SmartPy implementation

The SmartPy version uses a small `variant` state machine with `WAIT_DEPOSIT`, `WAIT_RECIPIENT`, and `CLOSED`.
The buyer must call `deposit()` with the exact amount, after which the buyer may call `pay()` or the seller may call `refund()`.
Both final actions close the contract state before transferring funds.

## Differences with Solidity/Ethereum

- The SmartPy implementation makes the state transitions explicit with a `variant`, instead of a Solidity enum.