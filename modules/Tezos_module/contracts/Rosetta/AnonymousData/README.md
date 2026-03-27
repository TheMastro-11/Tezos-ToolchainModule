# Anonymous data

## Specification

This contract allows users to store data on-chain. Stored data is associated with a cryptographic hash in a way that only the user who can generate that hash can retrieve it.

Once the contract is deployed, it supports the following actions:
- **getID**: the user gets the cryptographic hash of their address, salted with a freely chosen nonce passed as an argument.
- **store_data**: if data is not already associated, the user associates binary data to their ID, as obtained with `getID`.
- **getMyData**: the user passes the nonce used to generate the ID and retrieves the stored data.

Note: a user can always use a new nonce to generate a new ID and store new data.

## Required functionalities

- Dynamic arrays
- Bounded loops
- Transaction revert
- Hash on arbitrary messages

## SmartPy implementation

The SmartPy implementation stores data in a `big_map[bytes, bytes]` called `storedData`.
`getID` and `getMyData` are implemented as **on-chain views** and compute the identifier with `sp.keccak(sp.pack((sp.sender, nonce)))`.
The write path is handled by the `store_data` entrypoint, which rejects duplicate identifiers.

## Differences with Solidity/Ethereum

- In SmartPy, read-only queries are exposed as **on-chain views** (`getID`, `getMyData`) instead of Solidity-style `view` functions.
- The hash input is built with `sp.pack(...)` before calling `sp.keccak`, whereas the Solidity version relies on Solidity ABI encoding helpers.
- Storage uses a Tezos `big_map` keyed by `bytes`, which is the SmartPy counterpart of the Solidity mapping-based design.
