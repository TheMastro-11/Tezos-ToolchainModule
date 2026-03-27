import smartpy as sp
import requests

@sp.module
def main():
    class HTLCRosetta(sp.Contract):
        def __init__(self, owner: sp.address, v: sp.address, h: sp.bytes, delay: sp.nat):
            self.data.owner = owner
            self.data.verifier = v
            self.data.hash = h
            self.data.reveal_timeout = sp.level + delay

        @sp.entrypoint
        def reveal(self, s: sp.string):
            assert sp.balance - sp.amount >= sp.mutez(1) #check solidity constructor
            
            assert sp.sender == self.data.owner
            assert sp.keccak(sp.pack(s)) == self.data.hash
        
            sp.send(self.data.owner, sp.balance)

        @sp.entrypoint
        def timeout(self):
            assert sp.level >= self.data.reveal_timeout, "Timeout not reached"
            sp.send(self.data.verifier, sp.balance)

@sp.add_test()
def test():
    sc = sp.test_scenario("HTLCRosetta", main)
    owner = sp.address("tz1SL2xBdmLSD2W3Hs84SfH912xDpYtAjsaa")
    verifier = sp.address("tz1aLPm3WynyHRXFvjjdHZDKEjHZVvQMGxqU")
    secret = "Test"
    secret_hash = sp.keccak(sp.pack(secret))
    delay = sp.nat(30)
    
    rpc = "https://rpc.tzkt.io/ghostnet"
    head = requests.get(f"{rpc}/chains/main/blocks/head/header").json()
    current_level = int(head["level"])
    
    empty_htlc = main.HTLCRosetta(owner, verifier, secret_hash, delay + current_level)
    sc += empty_htlc