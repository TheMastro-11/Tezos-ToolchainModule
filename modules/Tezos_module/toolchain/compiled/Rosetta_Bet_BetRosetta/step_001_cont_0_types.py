import smartpy as sp

tstorage = sp.record(deadline=sp.nat, oracle=sp.address, player1=sp.address, player2=sp.option[sp.address], wager=sp.mutez).layout(("deadline", ("oracle", ("player1", ("player2", "wager")))))
tparameter = sp.variant(join=sp.unit, timeout=sp.unit, win=sp.nat).layout(("join", ("timeout", "win")))
tprivates = { }
tviews = { }
