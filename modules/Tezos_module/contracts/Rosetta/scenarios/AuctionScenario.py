from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Auction.AuctionRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("AuctionRosetta", main)

    seller = sp.test_account("seller")
    alice = sp.test_account("alice")
    bob = sp.test_account("bob")

    auction = main.AuctionRosetta(seller.address, "reason", sp.mutez(5))
    auction.set_initial_balance(sp.mutez(5))
    sc += auction

    sc.verify(auction.data.state == sp.variant.WAIT_START(sp.unit))
    sc.verify(auction.data.highest_bid == sp.mutez(5))
    sc.verify(~auction.data.highest_bidder.is_some())

    auction.start(100, _sender=alice.address, _now=sp.timestamp(0), _valid=False)
    auction.start(100, _sender=seller.address, _now=sp.timestamp(0))
    auction.start(100, _sender=seller.address, _now=sp.timestamp(1), _valid=False)

    sc.verify(auction.data.state == sp.variant.WAIT_CLOSING(sp.unit))
    sc.verify(auction.data.end_time.unwrap_some() == sp.timestamp(100))

    auction.bid(_sender=alice.address, _amount=sp.mutez(5), _now=sp.timestamp(10), _valid=False)
    auction.bid(_sender=alice.address, _amount=sp.mutez(10), _now=sp.timestamp(10))
    auction.withdraw(_sender=alice.address, _now=sp.timestamp(20))

    auction.end(_sender=seller.address, _now=sp.timestamp(50), _valid=False)
    auction.end(_sender=bob.address, _now=sp.timestamp(101), _valid=False)
    auction.end(_sender=seller.address, _now=sp.timestamp(101))

    sc.verify(auction.data.state == sp.variant.CLOSED(sp.unit))
    auction.bid(_sender=bob.address, _amount=sp.mutez(25), _now=sp.timestamp(102), _valid=False)
    auction.withdraw(_sender=bob.address, _now=sp.timestamp(103), _valid=False)

    
    auction2 = main.AuctionRosetta(seller.address, "reason", sp.mutez(5))
    sc += auction2
    
    auction2.start(5, _sender=seller.address, _now=sp.timestamp(0))
    auction2.bid(_sender=bob.address, _amount=sp.mutez(25), _now=sp.timestamp(1))
    auction2.withdraw(_sender=bob.address, _now=sp.timestamp(3))
    auction2.end(_sender=seller.address, _now=sp.timestamp(6))


