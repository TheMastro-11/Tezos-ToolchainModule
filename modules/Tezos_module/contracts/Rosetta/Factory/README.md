# Factory

## Specification

The Factory contract allows a user to create and deploy another contract (called Product contract), according to the [Factory Pattern](https://betterprogramming.pub/learn-solidity-the-factory-pattern-75d11c3e7d29).

Once the Factory contract has been deployed, it supports the following actions:
- **createProduct**: to create a Product contract, the user must specify a `tag` string to be stored in the Product state.
- **getProducts**: at any time, the user gets the list of addresses of their Product contracts.

Once a Product contract has been deployed, it supports the following actions:
- **getTag**: the owner gets the tag stored in the Product state.This action is only possible for the user who requested the creation of the Product contract.
- **getFactory**: anyone gets the address of the Factory contract that generated the Product.

## Required functionalities

- In-contract deployment
- Transaction revert
- Key-value maps
- Dynamic arrays

## SmartPy implementation

The SmartPy implementation contains two contracts in the same file: `FactoryRosetta` and `ProductRosetta`.
`createProduct()` uses `sp.create_contract(...)` to originate a new `ProductRosetta`, stores its address in `product_list`, and emits the new address.
The read APIs are implemented as **off-chain views**.

## Differences with Solidity/Ethereum

- Contract deployment is done through `sp.create_contract`, the SmartPy/Tezos counterpart of Solidity's `new`.
- `getTag` and `getFactory` are exposed as **off-chain views** instead of Solidity getter/view functions.
