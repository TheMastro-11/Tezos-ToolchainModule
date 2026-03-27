# Price Bet

## Specification

The PriceBet contract allows anyone to bet on a future exchange rate between two tokens.

The contract has the following parameters, defined at deployment time:
- an **owner**, who provides the initial pot in native cryptocurrency
- an **oracle**, a contract queried for the exchange rate
- a **deadline**, after which the player loses the bet
- an **exchange rate**, that must be reached in order for the player to win the bet

After creation, the following actions are possible:
- **join**: a player joins the contract by depositing an amount of native cryptocurrency equal to the initial pot
- **win**: after the join and before the deadline, the player can withdraw the whole pot if the oracle exchange rate is greater than or equal to the target rate
- **timeout**: after the deadline, the owner can redeem the whole pot

## Required functionalities

- Native tokens
- Time constraints
- Transaction revert
- Contract-to-contract calls

## SmartPy implementation

The SmartPy contract stores the owner's initial pot, the oracle address, the deadline block, the target exchange rate, and the optional player address.
The oracle exposes an **on-chain view** named `get_exchange_rate`, and `win()` reads it with `sp.view(...)`.
In the test scenario, the owner funds the contract at origination and the player matches that amount through `join()`.

## Differences with Solidity/Ethereum

- The SmartPy version performs the oracle query through a Tezos **on-chain view**, rather than a Solidity interface call.
- The owner address is explicitly passed and stored in the SmartPy constructor
