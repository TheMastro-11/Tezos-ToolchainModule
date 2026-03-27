from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PaymentSplitter.PaymentSplitterRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("PaymentSplitterRosetta", main)

    admin = sp.test_account("admin")
    mario = sp.test_account("mario")
    outsider = sp.test_account("outsider")

    payees = [
        admin.address,
        mario.address
    ]
    shares = [
        sp.nat(70),
        sp.nat(30)
    ]

    sc.h1("Main scenario")

    payment_splitter = main.PaymentSplitterRosetta(shares, payees)
    sc += payment_splitter

    sc.h2("Initial storage")
    sc.verify(payment_splitter.data.total_shares == sp.nat(100))
    sc.verify(payment_splitter.data.total_released == sp.mutez(0))
    sc.verify(payment_splitter.payee(sp.nat(0)) == admin.address)
    sc.verify(payment_splitter.payee(sp.nat(1)) == mario.address)
    sc.verify(payment_splitter.data.shares[admin.address] == sp.nat(50))
    sc.verify(payment_splitter.data.shares[mario.address] == sp.nat(30))

    sc.h2("Receiving funds")
    payment_splitter.receive(_sender=outsider.address, _amount=sp.mutez(10))
    sc.verify(payment_splitter.balance == sp.mutez(10))

    sc.h2("Release flow")
    payment_splitter.release(admin.address, _sender=admin.address)
    payment_splitter.release(mario.address, _sender=mario.address)

    sc.h2("No payment for non-payee")
    payment_splitter.release(outsider.address, _sender=outsider.address, _valid=False)
    
