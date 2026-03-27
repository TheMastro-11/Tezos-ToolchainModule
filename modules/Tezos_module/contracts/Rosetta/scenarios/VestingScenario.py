from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Vesting.VestingRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("VestingRosetta", main)

    beneficiary = sp.test_account("beneficiary")
    outsider = sp.test_account("outsider")
    start_level = sp.nat(5)
    duration = sp.nat(10)
    initial_balance = sp.mutez(10_000_000)

    vesting = main.VestingRosetta(beneficiary.address, start_level, duration)
    vesting.set_initial_balance(initial_balance)
    sc += vesting

    sc.h1("VestingRosetta scenario")

    sc.h2("Initial storage")
    sc.verify(vesting.data.beneficiary == beneficiary.address)
    sc.verify(vesting.data.start == start_level)
    sc.verify(vesting.data.duration == duration)
    sc.verify(vesting.data.released == sp.nat(0))
    sc.verify(vesting.balance == initial_balance)

    sc.h2("Static vesting configuration")
    sc.verify(vesting.data.start + vesting.data.duration == sp.nat(15))
    sc.verify(vesting.data.start < vesting.data.start + vesting.data.duration)
    sc.verify(beneficiary.address != outsider.address)

    sc.h2("Release entrypoint")
    vesting.release(_sender=outsider.address, _level=1)
    vesting.release(_sender=beneficiary.address, _level=5)
    vesting.release(_sender=beneficiary.address, _level=20)

    sc.verify(vesting.data.released == sp.nat(10000000))
    sc.verify(vesting.balance == sp.mutez(0))
