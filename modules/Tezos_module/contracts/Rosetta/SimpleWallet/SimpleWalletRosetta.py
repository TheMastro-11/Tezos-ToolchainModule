import smartpy as sp

@sp.module
def t():
    tx: type = sp.record(
        to=sp.address,
        value=sp.mutez,
        data=sp.bytes,
        executed=sp.bool
    )

@sp.module
def main():
    import smartpy.stdlib.utils as utils
    import t
    
    class SimpleWalletRosetta(sp.Contract):
        def __init__(self, owner: sp.address):
            assert owner != sp.address("0")
            self.data.transactions = sp.cast([], sp.list[t.tx])
            self.data.owner = owner

        @sp.entrypoint
        def deposit(self):
            assert sp.amount > sp.mutez(0)

        @sp.entrypoint
        def createTransaction(self, to: sp.address, value: sp.nat, data: sp.bytes):
            assert sp.sender == self.data.owner
            tx = sp.cast(sp.record(to=to, value=utils.nat_to_mutez(value), data=data, executed=False), t.tx)
            self.data.transactions = sp.cons(tx, self.data.transactions)
            
        @sp.entrypoint
        def executeTransaction(self, tx_id):
            assert sp.sender == self.data.owner, "Only the owner"
            assert tx_id < sp.len(self.data.transactions), "Transaction does not exist."
            counter = 0
            new_tx = sp.cast(None, sp.option[t.tx])
            for tx in self.data.transactions:
                if counter == tx_id:
                    assert tx.executed == False, "Transaction already executed."
                    new_tx = sp.Some(tx)
                    assert new_tx.unwrap_some().value < sp.balance, "Insufficient funds."
                    tx.executed = True
                    new_tx = sp.Some(tx)
            new_tx1 = new_tx.unwrap_some()
            sp.send(new_tx1.to, new_tx1.value)

        @sp.entrypoint
        def withdraw(self):
            assert sp.sender == self.data.owner, "Only the owner"
            sp.send(sp.sender, sp.balance)

@sp.add_test()
def test():
    sc = sp.test_scenario("SimpleWalletRosetta")
    owner = sp.address("tz1SL2xBdmLSD2W3Hs84SfH912xDpYtAjsaa")
    wallet = main.SimpleWalletRosetta(owner)
    sc += wallet