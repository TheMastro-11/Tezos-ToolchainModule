import smartpy as sp


@sp.module
def main():
    class CouponIssuer(sp.Contract):
        def __init__(self, admin):
            self.data.admin = admin

        @sp.entrypoint
        def issue(self, params):
            sp.cast(
                params,
                sp.record(
                    kind=sp.string,
                    amount=sp.nat,
                    receiver=sp.address,
                ),
            )

            assert sp.sender == self.data.admin, "NOT_ADMIN"
            assert params.amount > 0, "ZERO_AMOUNT"

            destination = sp.contract(
                sp.ticket[sp.string],
                params.receiver,
                entrypoint="receive_coupon",
            ).unwrap_some(error="BAD_RECEIVER")

            coupon = sp.ticket(params.kind, params.amount)
            sp.transfer(coupon, sp.mutez(0), destination)

    class CouponReceiver(sp.Contract):
        def __init__(self):
            self.data.received = sp.cast({}, sp.map[sp.string, sp.nat])
            self.data.last_ticketer = sp.cast(None, sp.option[sp.address])

        @sp.entrypoint
        def receive_coupon(self, coupon):
            sp.cast(coupon, sp.ticket[sp.string])

            (info, _copy) = sp.read_ticket(coupon)

            self.data.received[info.contents] = (
                self.data.received.get(info.contents, default=sp.nat(0)) + info.amount
            )
            self.data.last_ticketer = sp.Some(info.ticketer)


@sp.add_test()
def test():
    scenario = sp.test_scenario("simple_ticket_demo", main)

    admin = sp.test_account("admin")
    alice = sp.test_account("alice")

    issuer = main.CouponIssuer(admin.address)
    receiver = main.CouponReceiver()

    scenario += issuer
    scenario += receiver

    scenario.h1("Admin emette 3 coupon coffee")
    issuer.issue(
        kind="coffee",
        amount=sp.nat(3),
        receiver=receiver.address,
        _sender=admin,
    )

    scenario.verify(receiver.data.received["coffee"] == 3)
    scenario.verify(receiver.data.last_ticketer == sp.Some(issuer.address))

    scenario.h1("Admin emette altri 2 coupon meal")
    issuer.issue(
        kind="meal",
        amount=sp.nat(2),
        receiver=receiver.address,
        _sender=admin,
    )

    scenario.verify(receiver.data.received["meal"] == 2)
    scenario.verify(receiver.data.received["coffee"] == 3)

    scenario.h1("Utente non autorizzato")
    issuer.issue(
        kind="coffee",
        amount=sp.nat(1),
        receiver=receiver.address,
        _sender=alice,
        _valid=False,
        _exception="NOT_ADMIN",
    )

    scenario.h1("Importo zero non valido")
    issuer.issue(
        kind="coffee",
        amount=sp.nat(0),
        receiver=receiver.address,
        _sender=admin,
        _valid=False,
        _exception="ZERO_AMOUNT",
    )