# Lottery

## Specification

Consider a lottery where two players bet an equal amount of crypto-currency, and the winner - who is chosen fairly between the two players - redeems the whole pot.

Since smart contract are deterministic and external sources of randomness (e.g., random number oracles) might be biased, to achieve fairness we follow a *commit-reveal-punish* protocol, where both players first commit to the hash of the secret, then reveal their secret (which must be a preimage of the committed hash), and finally the winner is computed as a fair function of the secrets.

Implementing this protocol properly is quite error-prone, since the protocol must punish players who behave dishonestly, e.g. by refusing to perform some required action. In this case, the protocol must still ensure that, on average, an honest player has at least the same payoff that she would have by interacting with another honest player. 

The protocol followed by the players is:
1. `player0` joins by paying the bet and committing to a secret hash;
2. `player1` joins by paying the same bet and committing to a different secret hash;
3. `player0` reveals the first secret;
4. `player1` reveals the second secret;
5. if a player stops cooperating, the other one can redeem the pot after the relevant deadline;
6. once both secrets are revealed, the winner receives the whole pot.

## Required functionalities

- Native tokens
- Multisig transactions
- Time constraints
- Transaction revert
- Hash on arbitrary messages
- Bitstring operations
- **Randomness**

## SmartPy implementation

The SmartPy contract uses a `variant` status with phases such as `Join0`, `Join1`, `Reveal0`, `Reveal1`, `Win`, and `End`.
Each player commits with `sp.keccak(sp.pack(secret))` and later reveals the original string.
If one party does not continue, the other can call a dedicated redeem entrypoint after the block-level deadline.
The winner is determined from the parity of the combined secret lengths.

## Differences with Solidity/Ethereum

- State is represented as a SmartPy `variant` instead of a Solidity enum.
