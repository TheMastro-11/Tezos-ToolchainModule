from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Bet.BetRosetta import *

@sp.add_test()
def test():
    sc = sp.test_scenario("BetRosetta")

    player1 = sp.test_account("player1")
    player2 = sp.test_account("player2")
    player3 = sp.test_account("player3")
    oracle = sp.test_account("oracle")
    outsider = sp.test_account("outsider")
    timeout = sp.nat(10)
    wager = sp.mutez(500)

    #player2 joins and oracle pays player1.
    bet_player1 = main.BetRosetta(player1.address, oracle.address, timeout, wager)
    bet_player1.set_initial_balance(wager)
    sc += bet_player1

    sc.verify(bet_player1.data.player1 == player1.address)
    sc.verify(~bet_player1.data.player2.is_some())
    sc.verify(bet_player1.data.oracle == oracle.address)
    sc.verify(bet_player1.data.wager == wager)
    sc.verify(bet_player1.data.deadline == sp.nat(10))

    bet_player1.win(sp.nat(0), _sender=oracle.address, _valid=False)
    bet_player1.join(_sender=player2.address, _amount=sp.mutez(400), _level=1, _valid=False)
    bet_player1.join(_sender=player2.address, _amount=wager, _level=1)
    
    sc.verify(bet_player1.data.player2.unwrap_some() == player2.address)
    sc.verify(bet_player1.balance == sp.mutez(1000))

    bet_player1.join(_sender=player3.address, _amount=wager, _level=2, _valid=False)
    bet_player1.win(sp.nat(0), _sender=outsider.address, _valid=False)
    bet_player1.win(sp.nat(2), _sender=oracle.address, _valid=False)
    bet_player1.win(sp.nat(0), _sender=oracle.address)

    sc.verify(bet_player1.balance == sp.mutez(0))

    #oracle pays player2.
    bet_player2 = main.BetRosetta(player1.address, oracle.address, timeout, wager)
    bet_player2.set_initial_balance(wager)
    sc += bet_player2

    bet_player2.join(_sender=player2.address, _amount=wager, _level=3)
    bet_player2.win(sp.nat(1), _sender=oracle.address)

    sc.verify(bet_player2.balance == sp.mutez(0))

    # Timeout path with no second player.
    timeout_no_join = main.BetRosetta(player1.address, oracle.address, timeout, wager)
    timeout_no_join.set_initial_balance(wager)
    sc += timeout_no_join

    timeout_no_join.join(_sender=player2.address, _amount=wager, _level=10)
    timeout_no_join.timeout(_sender=player1.address, _level=9, _valid=False)
    timeout_no_join.timeout(_sender=player1.address, _level=14)

    sc.verify(timeout_no_join.balance == sp.mutez(0))

    # Timeout path after player2 joined; both wagers are refunded.
    timeout_with_join = main.BetRosetta(player1.address, oracle.address, timeout, wager)
    timeout_with_join.set_initial_balance(wager)
    sc += timeout_with_join

    timeout_with_join.join(_sender=player2.address, _amount=wager, _level=4)
    timeout_with_join.timeout(_sender=player2.address, _level=9, _valid=False)
    timeout_with_join.timeout(_sender=player2.address, _level=25)

    sc.verify(timeout_with_join.balance == sp.mutez(0))