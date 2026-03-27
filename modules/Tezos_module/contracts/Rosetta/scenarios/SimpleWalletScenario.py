from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from SimpleWallet.SimpleWalletRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("SimpleWalletRosetta", [t,main])
    
    owner = sp.test_account("owner")
    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    outsider = sp.test_account("outsider")

    sc.h1("Main scenario")

    wallet = main.SimpleWalletRosetta(owner.address)
    sc += wallet

    sc.h2("Initial storage")
    sc.verify(wallet.data.owner == owner.address)
    sc.verify(sp.len(wallet.data.transactions) == 0)
    sc.verify(wallet.balance == sp.mutez(0))

    sc.h2("Deposits")
    wallet.deposit(_sender=outsider.address, _amount=sp.mutez(0), _valid=False)
    wallet.deposit(_sender=outsider.address, _amount=sp.mutez(5_000_000))
    sc.verify(wallet.balance == sp.mutez(5_000_000))

    sc.h2("Create transactions")
    wallet.createTransaction(
        to=alice.address,
        value=sp.nat(2_000_000),
        data=sp.bytes("0x1234"),
        _sender=outsider.address,
        _valid=False,
    )

    wallet.createTransaction(
        to=alice.address,
        value=sp.nat(2_000_000),
        data=sp.bytes("0x1234"),
        _sender=owner.address,
    )
    wallet.createTransaction(
        to=bob.address,
        value=sp.nat(1_000_000),
        data=sp.bytes("0xabcd"),
        _sender=owner.address,
    )

    sc.verify(sp.len(wallet.data.transactions) == 2)

    sc.h2("Execute transactions")
    wallet.executeTransaction(sp.nat(0), _sender=outsider.address, _valid=False)
    wallet.executeTransaction(sp.nat(2), _sender=owner.address, _valid=False)
    wallet.executeTransaction(sp.nat(0), _sender=owner.address)
    wallet.executeTransaction(sp.nat(1), _sender=owner.address, _valid=False)
    sc.verify(sp.len(wallet.data.transactions) == 2)

    sc.h2("Withdraw remaining balance")
    wallet.withdraw(_sender=outsider.address, _valid=False)
    wallet.withdraw(_sender=owner.address)
    sc.verify(wallet.balance == sp.mutez(0))
