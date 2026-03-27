# Upgradeable Proxy

## Specification

This use case involves three contracts:
- **Logic** implements a logic to be stored on-chain;
- **Proxy** forwards a received call to an implementation contract and allows authorized upgrades of that implementation address;
- **Caller** invokes the logic through the proxy.

The Logic contract provides a function `check`.
The contracts are deployed in the following order: Logic, Proxy, Caller.
When creating the proxy contract, the creator specifies the address of the initial logic contract.

After creation, the contracts support the following actions:
- **Caller.callLogicByProxy**: allows a user to ask a proxy to execute `check`;
- **Proxy.upgradeTo**: allows the admin to update the implementation address.

## Required functionalities

- Contract update
- Transaction revert
- Contract-to-contract call
- Delegate call
- Dynamic arrays

## SmartPy implementation

The SmartPy file defines `ProxyRosetta`, `CallerRosetta`, and `LogicRosetta` together with two helper logic contracts used in the scenario.
`ProxyRosetta.check(balance)` forwards the call to the current logic contract by building a contract handle and sending the `balance` argument.
`upgradeTo(new_logic)` updates the implementation address when called by `admin`.

## Differences with Solidity/Ethereum

- This is **not a delegate-call-based proxy** like the Solidity. The SmartPy proxy forwards to another contract entrypoint through a regular contract call.
- Because Tezos/SmartPy does not offer Solidity-style delegate calls, storage is not shared with the logic contract in the same way.
- The current SmartPy implementation also simplifies the original example: `check` receives a `mutez` value directly, rather than reading the balance of an arbitrary address, because is **NOT** possible otherways.
- In practice, the SmartPy code demonstrates upgradeable routing, not a bytecode-level proxy identical to the Solidity one.
