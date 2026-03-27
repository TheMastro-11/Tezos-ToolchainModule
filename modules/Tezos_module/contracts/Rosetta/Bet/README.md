# Bet

## Specification

The Bet contract involves two players and an oracle. The contract has the following parameters, defined at deployment time:

- **player1**: the address of the first player;
- **oracle**: the address of a user acting as an oracle;
- **deadline**: a time limit expressed as a block-level offset;
- **wager**: the amount each player must stake in native cryptocurrency.

After creation, the following actions are possible:
- **join**: the second player joins the bet by depositing the wager;
- **win**: after both players have joined, the oracle selects the winner, who receives the whole pot;
- **timeout**: after the deadline, the wager(s) can be refunded.

## Required functionalities

- Native tokens
- Multisig transactions
- Time constraints
- Transaction revert

## SmartPy implementation

The SmartPy contract stores `player1` at deployment and leaves `player2` empty until `join()` is called.
The deadline is recorded as `sp.level + timeout`.
In the reference scenario, player1's wager is supplied as the initial contract balance, while player2 contributes by calling `join()`.
The oracle later resolves the bet through `win(winner)`.

## Differences with Solidity/Ethereum

- The SmartPy implementation is effectively a **two-step join flow**: player1 is fixed at origination and player2 joins later, because it is not possible to have the 'dual-join' call.
- The first player's stake is expected to be present in the contract balance at origination time, rather than being deposited by an explicit SmartPy entrypoint.
