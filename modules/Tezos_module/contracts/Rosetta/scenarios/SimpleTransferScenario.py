from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from SimpleTransfer.SimpleTransferRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("SimpleTransferRosetta", main)
    owner = sp.test_account("owner")
    recipient = sp.test_account("recipient")
    outsider = sp.test_account("outsider")

    sc.h1("Main scenario")

    sitr = main.SimpleTransferRosetta(owner.address, recipient.address)
    sc += sitr

    sc.h2("Initial storage")
    sc.verify(sitr.data.owner == owner.address)
    sc.verify(sitr.data.recipient == recipient.address)
    sc.verify(sitr.balance == sp.mutez(0))

    sc.h2("Deposits")
    sitr.deposit(_sender=outsider.address, _amount=sp.mutez(3_000_000), _valid=False)
    sitr.deposit(_sender=owner.address, _amount=sp.mutez(5_000_000))
    sitr.deposit(_sender=owner.address, _amount=sp.mutez(2_000_000))
    sc.verify(sitr.balance == sp.mutez(7_000_000))

    sc.h2("Withdraw access control")
    sitr.withdraw(sp.mutez(1_000_000), _sender=outsider.address, _valid=False)
    sitr.withdraw(sp.mutez(1_000_000), _sender=owner.address, _valid=False)

    sc.h2("Withdraw limits")
    sitr.withdraw(sp.mutez(8_000_000), _sender=recipient.address, _valid=False)
    sc.verify(sitr.balance == sp.mutez(7_000_000))

    sc.h2("Recipient withdrawals")
    sitr.withdraw(sp.mutez(2_000_000), _sender=recipient.address)
    sc.verify(sitr.balance == sp.mutez(5_000_000))

    sitr.withdraw(sp.mutez(5_000_000), _sender=recipient.address)
    sc.verify(sitr.balance == sp.mutez(0))
