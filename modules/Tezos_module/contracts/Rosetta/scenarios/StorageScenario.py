from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Storage.StorageRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("StorageRosetta", main)

    storage = main.StorageRosetta()
    sc += storage

    sc.h1("Main scenario")

    sc.h2("Initial storage")
    sc.verify(~storage.data.byte_sequence.is_some())
    sc.verify(~storage.data.text_string.is_some())

    sc.h2("Store bytes")
    first_bytes = sp.bytes("0x1234")
    second_bytes = sp.bytes("0xaabbccdd")

    storage.storeBytes(first_bytes)
    sc.verify(storage.data.byte_sequence.is_some())
    sc.verify(storage.data.byte_sequence.unwrap_some() == first_bytes)
    sc.verify(~storage.data.text_string.is_some())

    storage.storeBytes(second_bytes)
    sc.verify(storage.data.byte_sequence.unwrap_some() == second_bytes)

    sc.h2("Store strings")
    first_text = "Hello Rosetta"
    second_text = "Storage updated"

    storage.storeString(first_text)
    sc.verify(storage.data.text_string.is_some())
    sc.verify(storage.data.text_string.unwrap_some() == first_text)
    sc.verify(storage.data.byte_sequence.unwrap_some() == second_bytes)

    storage.storeString(second_text)
    sc.verify(storage.data.text_string.unwrap_some() == second_text)
