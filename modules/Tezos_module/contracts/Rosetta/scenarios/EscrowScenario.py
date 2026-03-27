from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Escrow.EscrowRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("EscrowRosetta")

    seller = sp.test_account("seller")
    buyer = sp.test_account("buyer")
    outsider = sp.test_account("outsider")
    amount = sp.mutez(1000)

    # Happy path: buyer deposits and then releases the funds to the seller.
    escrow_pay = main.EscrowRosetta(amount, buyer.address, seller.address)
    sc += escrow_pay

    sc.verify(escrow_pay.data.buyer == buyer.address)
    sc.verify(escrow_pay.data.seller == seller.address)
    sc.verify(escrow_pay.data.amount == amount)
    sc.verify(escrow_pay.data.state == sp.variant.WAIT_DEPOSIT(sp.unit))
    sc.verify(escrow_pay.balance == sp.mutez(0))

    escrow_pay.pay(_sender=buyer.address, _valid=False)
    escrow_pay.refund(_sender=seller.address, _valid=False)
    escrow_pay.deposit(_sender=outsider.address, _amount=amount, _valid=False)
    escrow_pay.deposit(_sender=buyer.address, _amount=sp.mutez(999), _valid=False)
    escrow_pay.deposit(_sender=buyer.address, _amount=amount)

    sc.verify(escrow_pay.data.state == sp.variant.WAIT_RECIPIENT(sp.unit))
    sc.verify(escrow_pay.balance == amount)

    escrow_pay.deposit(_sender=buyer.address, _amount=amount, _valid=False)
    escrow_pay.pay(_sender=outsider.address, _valid=False)
    escrow_pay.refund(_sender=buyer.address, _valid=False)
    escrow_pay.pay(_sender=buyer.address)

    sc.verify(escrow_pay.data.state == sp.variant.CLOSED(sp.unit))
    sc.verify(escrow_pay.balance == sp.mutez(0))

    escrow_pay.pay(_sender=buyer.address, _valid=False)
    escrow_pay.refund(_sender=seller.address, _valid=False)

    # Refund path: seller returns the escrowed funds to the buyer.
    escrow_refund = main.EscrowRosetta(amount, buyer.address, seller.address)
    sc += escrow_refund

    escrow_refund.deposit(_sender=buyer.address, _amount=amount)
    sc.verify(escrow_refund.data.state == sp.variant.WAIT_RECIPIENT(sp.unit))
    sc.verify(escrow_refund.balance == amount)

    escrow_refund.refund(_sender=outsider.address, _valid=False)
    escrow_refund.refund(_sender=seller.address)

    sc.verify(escrow_refund.data.state == sp.variant.CLOSED(sp.unit))
    sc.verify(escrow_refund.balance == sp.mutez(0))

    escrow_refund.pay(_sender=buyer.address, _valid=False)
    escrow_refund.refund(_sender=seller.address, _valid=False)
