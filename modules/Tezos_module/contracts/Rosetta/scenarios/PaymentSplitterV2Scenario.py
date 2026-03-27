from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from PaymentSplitter.PaymentSplitterRosettaV2 import *

sc = sp.test_scenario("PaymentSplitter")
alice = sp.test_account("alice")
bob = sp.test_account("bob")
charlie = sp.test_account("charlie")
sc.show({"alice": alice, "bob": bob, "charlie": charlie})

c1 = main.PaymentSplitter({alice.address: 10, bob.address: 20, charlie.address: 30})
sc += c1

c1.default(_amount=sp.tez(100))
c1.release(alice.address)
sc.verify(c1.data.released[alice.address] == sp.mutez(16_666_666))
c1.release(charlie.address)
sc.verify(c1.data.released[charlie.address] == sp.tez(50))