# Storage

## Specification

The Storage contract allows a user to store on-chain byte sequences and strings.

After contract creation, the contract supports two actions:
- **storeBytes**: allows the user to store a sequence of bytes;
- **storeString**: allows the user to store a string.

## Required functionalities

- Dynamic arrays

## SmartPy implementation

Each entrypoint simply overwrites the relevant field with a new value wrapped in `sp.Some(...)`.

## Differences with Solidity/Ethereum

- The SmartPy version models the two stored values as `option` types (`None` / `Some`) instead of relying on Solidity's default-zero initialization semantics.
