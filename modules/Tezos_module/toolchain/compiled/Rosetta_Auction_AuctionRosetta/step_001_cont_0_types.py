import smartpy as sp

tstorage = sp.record(bids = sp.big_map(sp.address, sp.mutez), end_time = sp.option(sp.timestamp), highest_bid = sp.mutez, highest_bidder = sp.option(sp.address), object = sp.string, seller = sp.address, state = sp.variant(CLOSED = sp.unit, WAIT_CLOSING = sp.unit, WAIT_START = sp.unit).layout(("CLOSED", ("WAIT_CLOSING", "WAIT_START")))).layout(("bids", ("end_time", ("highest_bid", ("highest_bidder", ("object", ("seller", "state")))))))
tparameter = sp.variant(bid = sp.unit, end = sp.unit, start = sp.int, withdraw = sp.unit).layout((("bid", "end"), ("start", "withdraw")))
tprivates = { }
tviews = { }
