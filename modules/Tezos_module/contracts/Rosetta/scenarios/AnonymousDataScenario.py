from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from AnonymousData.AnonymousDataRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("AnonymousDataRosetta")
    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    c1 = main.AnonymousDataRosetta()
    sc += c1

    alice_nonce = sp.nat(1)
    bob_nonce = sp.nat(2)
    alice_data = sp.bytes("0x1234")
    bob_data = sp.bytes("0xabcd")

    alice_id = sp.keccak(sp.pack((alice.address, alice_nonce)))
    bob_id = sp.keccak(sp.pack((bob.address, bob_nonce)))

    sc.verify(alice_id != bob_id)

    c1.store_data(data=alice_data, id=alice_id, _sender=alice.address)
    c1.store_data(data=bob_data, id=bob_id, _sender=bob.address)
    c1.store_data(data=alice_data, id=alice_id, _sender=alice.address, _valid=False)

    sc.verify(c1.data.storedData[alice_id] == alice_data)
    sc.verify(c1.data.storedData[bob_id] == bob_data)
