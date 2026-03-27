import smartpy as sp

@sp.module
def main():
    class StorageRosetta(sp.Contract):
        def __init__(self):
            self.data.byte_sequence = sp.cast(None, sp.option[sp.bytes])
            self.data.text_string = sp.cast(None, sp.option[sp.string])

        @sp.entrypoint
        def storeBytes(self, byte_sequence: sp.bytes):
            self.data.byte_sequence = sp.Some(byte_sequence)

        @sp.entrypoint
        def storeString(self, text_string: sp.string):
            self.data.text_string = sp.Some(text_string)

@sp.add_test()
def test():
    sc = sp.test_scenario("StorageRosetta", main)
    storage = main.StorageRosetta()
    sc += storage