# Ticket / Coupon Generator in SmartPy

This smart contract provides a simple example of how to use **tickets** in SmartPy on Tezos.

The file contains two contracts:

- **`CouponIssuer`**: a contract that issues coupons in the form of tickets
- **`CouponReceiver`**: a contract that receives tickets and keeps track of the coupons it has received

The example also includes a **test scenario** that verifies the expected behavior of the system.

---

## Overview

The contract implements a very simple flow:

1. An authorized **admin** issues a coupon
2. The coupon is created as a **`string` ticket**
3. The ticket is transferred to a receiver contract
4. The receiver reads the ticket and updates its internal state

Coupons are identified by a string, for example:

- `coffee`
- `meal`

and each coupon has an associated quantity (`amount`).

---

## Project structure

### `CouponIssuer`

This contract is responsible for issuing coupons.

#### Storage

- `admin : address`  
  The address authorized to issue coupons

#### Entrypoint

##### `issue(params)`

Expected parameters:

- `kind : string` — coupon type
- `amount : nat` — coupon quantity
- `receiver : address` — address of the destination contract

#### Logic

The entrypoint:

- checks that the caller is the admin
- checks that the amount is greater than zero
- creates a `ticket[string]`
- transfers the ticket to the destination contract through the `receive_coupon` entrypoint

#### Possible errors

- `NOT_ADMIN` — if the caller is not the administrator
- `ZERO_AMOUNT` — if `amount == 0`
- `BAD_RECEIVER` — if the receiver does not expose the correct entrypoint or does not accept the expected type

---

### `CouponReceiver`

This contract receives coupons and stores the received information.

#### Storage

- `received : map[string, nat]`  
  A map that associates each coupon type with the total quantity received

- `last_ticketer : option[address]`  
  The address of the last contract that issued a received ticket

#### Entrypoint

##### `receive_coupon(coupon)`

Expected parameters:

- `coupon : ticket[string]`

#### Logic

The entrypoint:

- reads the received ticket with `sp.read_ticket`
- extracts:
  - `contents` → the coupon type
  - `amount` → the quantity
  - `ticketer` → the contract that created the ticket
- updates the `received` map
- stores the issuing contract address in `last_ticketer`

---

## Example flow

In the included test:

1. The admin issues **3 `coffee` coupons**
2. The receiver records:
   - `received["coffee"] == 3`
   - `last_ticketer == issuer.address`

Then:

3. The admin issues **2 `meal` coupons**
4. The receiver updates its state:
   - `received["meal"] == 2`
   - `received["coffee"] == 3`

Two error cases are also tested:

- an unauthorized user tries to issue coupons → `NOT_ADMIN`
- the admin tries to issue a zero amount → `ZERO_AMOUNT`

---

## Technical details

### Ticket type

The coupon is represented as:

- `ticket[string]`

The ticket content is therefore a string identifying the coupon category, while the quantity is handled by the ticket itself.

### Security / constraints

The contract enforces a few basic constraints:

- only the admin can issue coupons
- coupons with zero quantity cannot be issued
- the receiver must be compatible with the `receive_coupon` entrypoint

---

## Possible extensions

This example is intentionally minimal, but it can be extended in several ways:

- add coupon **revocation** or **burning**
- support multiple administrators
- attach metadata to coupons
- restrict the allowed coupon types
- store an issuance history
- add expiration or validity checks

---

## Tests

The file includes a test scenario with `@sp.add_test()` that verifies:

- successful issuance by the admin
- correct receiver state updates
- rejection of unauthorized callers
- rejection of zero-amount issuance

---

## Educational use case

This project is useful for understanding:

- how to create and transfer **tickets** in SmartPy
- how to define interoperable contracts
- how to validate permissions and inputs
- how to read the data contained in a received ticket

---

## Main file

- `TicketGenerator.py`

---

## Notes

This repository is intended as an educational and demonstrative example.  
Before using it in production, it is recommended to add:

- stronger security checks
- more robust error handling
- more complete tests
- deployment and operational documentation

---