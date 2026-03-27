import smartpy as sp
import TokenContract.TokenContract as tc

maint = tc.main
maintct = tc.t

@sp.module
def main():
    class ConstantProductAmmRosetta(sp.Contract):
        def __init__(self, t0, t1):
            self.data.t0 = sp.cast(t0, sp.address)
            self.data.t1 = sp.cast(t1, sp.address)
            self.data.r0 = sp.cast(0, sp.nat)
            self.data.r1 = sp.cast(0, sp.nat)
            self.data.ever_deposited = sp.cast(False, sp.bool)
            self.data.supply = sp.cast(0, sp.nat)
            self.data.minted = sp.cast({}, sp.big_map[sp.address, sp.nat])

        @sp.private()
        def transfer_in_(self, token_address, amount):
            sp.cast(token_address, sp.address)
            sp.cast(amount, sp.nat)

            if amount > 0:
                transfer_handle = sp.contract(
                    maintct.transfer_params,
                    token_address,
                    entrypoint="transfer",
                ).unwrap_some()

                sp.transfer(
                    [
                        sp.record(
                            from_=sp.sender,
                            txs=[
                                sp.record(
                                    to_=sp.self_address,
                                    token_id=sp.nat(0),
                                    amount=amount,
                                )
                            ],
                        )
                    ],
                    sp.mutez(0),
                    transfer_handle,
                )
                
        @sp.private()
        def transfer_out_(self, token_address, recipient, amount):
            sp.cast(token_address, sp.address)
            sp.cast(recipient, sp.address)
            sp.cast(amount, sp.nat)

            if amount > 0:
                transfer_handle = sp.contract(
                    maintct.transfer_params,
                    token_address,
                    entrypoint="transfer",
                ).unwrap_some()

                sp.transfer(
                    [
                        sp.record(
                            from_=sp.self_address,
                            txs=[
                                sp.record(
                                    to_=recipient,
                                    token_id=sp.nat(0),
                                    amount=amount,
                                )
                            ],
                        )
                    ],
                    sp.mutez(0),
                    transfer_handle,
                )

        @sp.private()
        def request_balance_check_(self, token_address, callback_name):
            sp.cast(token_address, sp.address)
            sp.cast(callback_name, sp.string)

            balance_of_handle = sp.contract(
                maintct.balance_of_params,
                token_address,
                entrypoint="balance_of",
            ).unwrap_some()

            sp.transfer(
                sp.record(
                    requests=[
                        sp.record(
                            owner=sp.self_address,
                            token_id=sp.nat(0),
                        )
                    ],
                    callback=sp.self_entrypoint(callback_name),
                ),
                sp.mutez(0),
                balance_of_handle,
            )

        @sp.entrypoint
        def deposit(self, x0, x1):
            assert x0 >= 0 and x1 >= 0, "Incorrect amount for x0 and x1"

            self.transfer_in_(self.data.t0, x0)
            self.transfer_in_(self.data.t1, x1)

            if self.data.ever_deposited:
                assert (self.data.r0 * x1) == (self.data.r1 * x0)
                toMint = (x0 * self.data.supply) / self.data.r0
            else:
                self.data.ever_deposited = True
                toMint = x0

            assert toMint > 0, "Incorrect amount for ToMint"
            self.data.minted = sp.update_map(
                sp.sender,
                sp.Some(self.data.minted[sp.sender] + toMint),
                self.data.minted,
            )
            self.data.supply = self.data.supply + toMint
            self.data.r0 = self.data.r0 + x0
            self.data.r1 = self.data.r1 + x1

            self.request_balance_check_(self.data.t0, "receive_balance_t0")
            self.request_balance_check_(self.data.t1, "receive_balance_t1")

        @sp.entrypoint
        def receive_balance_t0(self, responses):
            sp.cast(responses, list[maintct.balance_of_response])
            assert len(responses) == 1, "INVALID_BALANCE_RESPONSE_COUNT"

            response = responses[0]
            assert response.request.owner == sp.self_address, "INVALID_BALANCE_OWNER"
            assert response.request.token_id == sp.nat(0), "INVALID_TOKEN_ID"
            assert response.balance == self.data.r0, "INVALID_R0_BALANCE"

        @sp.entrypoint
        def receive_balance_t1(self, responses):
            sp.cast(responses, list[maintct.balance_of_response])
            assert len(responses) == 1, "INVALID_BALANCE_RESPONSE_COUNT"

            response = responses[0]
            assert response.request.owner == sp.self_address, "INVALID_BALANCE_OWNER"
            assert response.request.token_id == sp.nat(0), "INVALID_TOKEN_ID"
            assert response.balance == self.data.r1, "INVALID_R1_BALANCE"
            
        @sp.entrypoint
        def redeem(self, x):
            assert self.data.minted[sp.sender] >= x, "Not enough token"
            assert x < self.data.supply, "Not enough supply"
            
            x0 = (x * self.data.r0) / self.data.supply
            x1 = (x * self.datar1) / self.datasupply
            
            self.transfer_out_(self.data.t0, sp.sender, x0)
            self.transfer_out_(self.data.t1, sp.sender, x1)
            
            self.data.r0 = self.data.r0 - x0
            self.data.r1 = self.data.r1 - x1
            self.data.supply = self.data.supply - x
            self.data.minted = sp.update_map(
                sp.sender,
                sp.Some(self.data.minted[sp.sender] - x),
                self.data.minted,
            )
            
            self.request_balance_check_(self.data.t0, "receive_balance_t0")
            self.request_balance_check_(self.data.t1, "receive_balance_t1")
            
        @sp.entrypoint
        def swap(self, t, x_in, x_ouy_min):
            t = sp.cast(t, sp.address)
            assert t == self.data.t0 or t == self.data.t1, "Wrong token contract address"
            
            is_t0 = t == self.data.t0
            
            
            
            
            
            
