import smartpy as sp

@sp.module
def main():
    class PaymentSplitter(sp.Contract):
        def __init__(self, shares: sp.map[sp.address, sp.nat]):
            self.data.shares = shares
            self.data.total_shares = sp.sum(shares.values())
            self.data.released = sp.cast({}, sp.map[sp.address, sp.mutez])
            self.data.total_released = sp.tez(0)

            for account in shares.keys():
                self.data.released[account] = sp.tez(0)

        @sp.entrypoint
        def default(self):
            """Allows anyone to deposit cryptocurrency units in the contract"""
            pass

        @sp.entrypoint
        def release(self, account: sp.address):
            """Allows anyone to distribute the contract balance to the shareholders.
            Each shareholder will receive an amount proportional to the percentage of total shares they were assigned.
            The contract follows a pull payment model:
                this means that each shareholder will receive the corresponding amount in a separate call to the release function.
            """
            # total funds ever received by the contract
            total_received = sp.balance + self.data.total_released

            # account's cumulative entitlement
            entitled = sp.split_tokens(
                total_received,
                self.data.shares[account],
                self.data.total_shares
            )

            if entitled > self.data.released[account]:
                payment = entitled - self.data.released[account]
                self.data.released[account] += payment
                self.data.total_released += payment
                sp.send(account, payment)
