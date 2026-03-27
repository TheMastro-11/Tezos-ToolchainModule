from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Lottery.LotteryRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("LotteryRosetta", main)

    owner = sp.test_account("owner")
    player0 = sp.test_account("player0")
    player1 = sp.test_account("player1")

    secret0 = "alpha"
    hash0 = sp.keccak(sp.pack(secret0))
    bet_amount = sp.mutez(1_000_000)

    lottery = main.LotteryRosetta(owner.address)
    sc += lottery

    sc.verify(lottery.data.owner == owner.address)
    sc.verify(lottery.data.bet_amount == sp.mutez(0))
    sc.verify(lottery.data.secret0 == "")
    sc.verify(lottery.data.secret1 == "")
    sc.verify(lottery.balance == sp.mutez(0))

    lottery.join0(hash0, _sender=player0.address, _amount=sp.mutez(0), _valid=False)
    lottery.redeem0_nojoin1(_sender=player0.address, _level=999, _valid=False)

    lottery.join0(hash0, _sender=player0.address, _amount=bet_amount, _level=1)

    sc.verify(lottery.data.player0.unwrap_some() == player0.address)
    sc.verify(lottery.data.hash0.unwrap_some() == hash0)
    sc.verify(lottery.data.bet_amount == bet_amount)
    sc.verify(lottery.balance == bet_amount)

    lottery.join0(hash0, _sender=player1.address, _amount=bet_amount, _level=2, _valid=False)
    lottery.redeem0_nojoin1(_sender=player0.address, _level=1000, _valid=False)
    lottery.redeem0_nojoin1(_sender=player0.address, _level=1001)

    sc.verify(lottery.balance == sp.mutez(0))
    sc.verify(lottery.data.status == sp.variant.End(sp.unit))
