from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from HTLC.HTLCRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("HTLCRosetta", main)

    owner = sp.test_account("owner")
    verifier = sp.test_account("verifier")
    outsider = sp.test_account("outsider")
    secret = "Test"
    wrong_secret = "Wrong"
    secret_hash = sp.keccak(sp.pack(secret))
    delay = sp.nat(10)

    # The contract requires an existing balance before reveal can succeed.
    empty_htlc = main.HTLCRosetta(owner.address, verifier.address, secret_hash, delay)
    sc += empty_htlc

    sc.verify(empty_htlc.data.owner == owner.address)
    sc.verify(empty_htlc.data.verifier == verifier.address)
    sc.verify(empty_htlc.data.hash == secret_hash)
    sc.verify(empty_htlc.data.reveal_timeout == sp.nat(10))
    sc.verify(empty_htlc.balance == sp.mutez(0))

    empty_htlc.reveal(secret, _sender=owner.address, _valid=False)

    funded_htlc = main.HTLCRosetta(owner.address, verifier.address, secret_hash, delay)
    funded_htlc.set_initial_balance(sp.mutez(1_000_000))
    sc += funded_htlc

    sc.verify(funded_htlc.data.owner == owner.address)
    sc.verify(funded_htlc.data.verifier == verifier.address)
    sc.verify(funded_htlc.data.hash == secret_hash)
    sc.verify(funded_htlc.data.reveal_timeout == sp.nat(10))
    sc.verify(funded_htlc.balance == sp.mutez(1_000_000))

    funded_htlc.reveal(secret, _sender=outsider.address, _valid=False)
    funded_htlc.reveal(wrong_secret, _sender=owner.address, _valid=False)
    funded_htlc.reveal(secret, _sender=owner.address)

    sc.verify(funded_htlc.balance == sp.mutez(0))
