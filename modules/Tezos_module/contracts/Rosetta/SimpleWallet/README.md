# Simple Wallet

## Specification

The SimpleWallet contract acts as a native cryptocurrency deposit, and it allows for the creation and execution of transactions to a specific address.
The owner can withdraw the total amount of cryptocurrency in the balance at any time.

The owner initializes the contract by specifying the address to authorize.

After contract creation, the contract supports the following actions:
- **deposit**: allows the owner to deposit native cryptocurrency;
- **createTransaction**: allows the owner to create a transaction with recipient, value, and data;
- **executeTransaction**: allows the owner to execute a stored transaction by ID;
- **withdraw**: allows the owner to withdraw the entire contract balance.

## Required functionalities

- Native tokens
- Transaction revert
- Dynamic arrays

## SmartPy implementation

Transactions are stored as a `list` of records containing `to`, `value`, `data`, and `executed`.
The owner appends new transactions through `createTransaction(...)` and later executes one through `executeTransaction(tx_id)`.
Execution scans the list, validates the selected transaction, marks it as executed in memory, and transfers the requested amount.

## Differences with Solidity/Ethereum

- The SmartPy implementation uses a `list` of transaction records rather than the Solidity array-of-structs style, but the conceptual model is the same.
- Execution iterates through the list explicitly, which is typical in SmartPy when updating a selected element.