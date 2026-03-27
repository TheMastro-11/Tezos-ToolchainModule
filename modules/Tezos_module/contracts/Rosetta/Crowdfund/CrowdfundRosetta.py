import smartpy as sp
import requests

@sp.module
def main():
    class CrowdfundRosetta(sp.Contract):
        def __init__(self, receiver: sp.address, end_donate: sp.nat, goal: sp.mutez):
            self.data.end_donate = sp.level + end_donate
            self.data.goal = goal
            self.data.receiver = receiver
            self.data.donors = sp.cast(sp.big_map(), sp.big_map[sp.address, sp.mutez])

        @sp.entrypoint
        def donate(self):
            assert sp.level < self.data.end_donate, "Timeout"
            if self.data.donors.contains(sp.sender):
                self.data.donors[sp.sender] += sp.amount
            else:
                self.data.donors[sp.sender] = sp.amount
            
        @sp.entrypoint
        def withdraw(self):
            assert sp.level >= self.data.end_donate, "The timeout has not passed"
            assert sp.balance >= self.data.goal, "Goal not reached"
            
            sp.send(self.data.receiver, sp.balance)

        @sp.entrypoint
        def reclaim(self):
            assert sp.level >= self.data.end_donate, "The timeout has not passed"
            assert sp.balance < self.data.goal, "Goal reached"
            assert self.data.donors[sp.sender] > sp.mutez(0)
            amount = self.data.donors[sp.sender]
            self.data.donors[sp.sender] = sp.mutez(0)
            
            sp.send(sp.sender, amount)
            
@sp.add_test()
def test():
    sc = sp.test_scenario("CrowdfundRosetta")
    receiver = sp.address("tz1aLPm3WynyHRXFvjjdHZDKEjHZVvQMGxqU")
    end_donate = sp.nat(30)
    goal = sp.mutez(100)
    
    rpc = "https://rpc.tzkt.io/ghostnet"
    head = requests.get(f"{rpc}/chains/main/blocks/head/header").json()
    current_level = int(head["level"])
    
    successful = main.CrowdfundRosetta(receiver, end_donate + current_level, goal)
    sc += successful
