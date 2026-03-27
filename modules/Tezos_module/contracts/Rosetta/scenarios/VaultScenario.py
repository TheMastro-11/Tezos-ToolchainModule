from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Vault.VaultRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("VaultRosetta", main)

    owner = sp.test_account("owner")
    recovery = sp.test_account("recovery")
    receiver = sp.test_account("receiver")
    outsider = sp.test_account("outsider")
    wait_time = sp.nat(10)

    vault = main.VaultRosetta(owner.address, recovery.address, wait_time)
    sc += vault

    sc.h1("VaultRosetta scenario")

    sc.h2("Initial storage")
    sc.verify(vault.data.owner == owner.address)
    sc.verify(vault.data.recovery == recovery.address)
    sc.verify(vault.data.wait_time == wait_time)
    sc.verify(vault.data.receiver == None)
    sc.verify(vault.data.request_time == None)
    sc.verify(vault.data.amount == sp.mutez(0))
    sc.verify(vault.data.state == sp.variant.IDLE(sp.unit))
    sc.verify(vault.balance == sp.mutez(0))

    sc.h2("Receive funds")
    vault.receive(_sender=outsider.address, _amount=sp.mutez(0), _valid=False)
    vault.receive(_sender=outsider.address, _amount=sp.mutez(5_000_000))
    sc.verify(vault.balance == sp.mutez(5_000_000))

    sc.h2("Withdraw request")
    vault.withdraw(sp.record(amount=sp.nat(1_000_000), receiver=receiver.address), _sender=outsider.address, _valid=False)
    vault.withdraw(sp.record(amount=sp.nat(6_000_000), receiver=receiver.address), _sender=owner.address, _valid=False)
    vault.withdraw(sp.record(amount=sp.nat(1_000_000), receiver=receiver.address), _sender=owner.address, _level=7)

    sc.verify(vault.data.receiver.unwrap_some() == receiver.address)
    sc.verify(vault.data.request_time.unwrap_some() == sp.nat(7))
    sc.verify(vault.data.amount == sp.mutez(1_000_000))
    sc.verify(vault.data.state == sp.variant.REQ(sp.unit))
    sc.verify(vault.balance == sp.mutez(5_000_000))

    sc.h2("Finalize constraints")
    vault.withdraw(sp.record(amount=sp.nat(1), receiver=receiver.address), _sender=owner.address, _valid=False)
    vault.cancel(_sender=outsider.address, _valid=False)
    vault.finalize(_sender=outsider.address, _level=17, _valid=False)
    vault.finalize(_sender=owner.address, _level=16, _valid=False)

    sc.h2("Recovery cancels request")
    vault.cancel(_sender=recovery.address)
    sc.verify(vault.data.state == sp.variant.IDLE(sp.unit))
    sc.verify(vault.balance == sp.mutez(5_000_000))

    sc.h2("Second withdraw cycle")
    vault.finalize(_sender=owner.address, _level=30, _valid=False)
    vault.cancel(_sender=recovery.address, _valid=False)
    vault.withdraw(sp.record(amount=sp.nat(2_500_000), receiver=receiver.address), _sender=owner.address, _level=20)
    vault.finalize(_sender=owner.address, _level=29, _valid=False)
    vault.finalize(_sender=owner.address, _level=30)

    sc.verify(vault.data.state == sp.variant.IDLE(sp.unit))
    sc.verify(vault.balance == sp.mutez(2_500_000))

    sc.h2("Post-finalize state")
    vault.cancel(_sender=recovery.address, _valid=False)
    vault.finalize(_sender=owner.address, _level=31, _valid=False)
