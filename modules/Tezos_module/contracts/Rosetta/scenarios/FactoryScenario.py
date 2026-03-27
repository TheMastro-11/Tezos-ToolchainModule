from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from Factory.FactoryRosetta import *

@sp.add_test()
def testWallet():
    sc = sp.test_scenario("FactoryRosetta", main)

    alice = sp.test_account("alice")
    bob = sp.test_account("bob")
    charlie = sp.test_account("charlie")

    factory = main.FactoryRosetta()
    sc += factory

    sc.verify(sp.catch_exception(factory.getProducts(alice.address)) == sp.Some("Address not avaiable"))
    sc.verify(sp.catch_exception(factory.getProducts(bob.address)) == sp.Some("Address not avaiable"))
    sc.verify(sp.catch_exception(factory.getProducts(charlie.address)) == sp.Some("Address not avaiable"))

    factory.createProduct("alice-first", _sender=alice.address)
    factory.createProduct("alice-second", _sender=alice.address)
    factory.createProduct("bob-only", _sender=bob.address)

    first_product = sc.dynamic_contract(main.ProductRosetta, offset=-3)
    second_product = sc.dynamic_contract(main.ProductRosetta, offset=-2)
    third_product = sc.dynamic_contract(main.ProductRosetta, offset=-1)

    sc.verify(sp.len(factory.data.product_list[alice.address]) == 2)
    sc.verify(sp.len(factory.data.product_list[bob.address]) == 1)
    sc.verify(sp.catch_exception(factory.getProducts(charlie.address)) == sp.Some("Address not avaiable"))

    alice_products = sc.compute(factory.getProducts(alice.address))
    bob_products = sc.compute(factory.getProducts(bob.address))

    sc.verify(sp.len(alice_products) == 2)
    sc.verify(sp.len(bob_products) == 1)
    sc.verify_equal(alice_products, [second_product.address, first_product.address])
    sc.verify_equal(bob_products, [third_product.address])

    sc.verify_equal(first_product.data.owner, alice.address)
    sc.verify_equal(first_product.data.factory, factory.address)
    sc.verify_equal(first_product.data.tag, "alice-first")

    sc.verify_equal(second_product.data.owner, alice.address)
    sc.verify_equal(second_product.data.factory, factory.address)
    sc.verify_equal(second_product.data.tag, "alice-second")

    sc.verify_equal(third_product.data.owner, bob.address)
    sc.verify_equal(third_product.data.factory, factory.address)
    sc.verify_equal(third_product.data.tag, "bob-only")

    sc.verify_equal(sc.compute(first_product.getFactory()), factory.address)
    sc.verify_equal(sc.compute(second_product.getFactory()), factory.address)
    sc.verify_equal(sc.compute(third_product.getFactory()), factory.address)

    sc.verify_equal(first_product.data.tag, "alice-first")
    sc.verify_equal(second_product.data.tag, "alice-second")
    sc.verify_equal(third_product.data.tag, "bob-only")

    sc.verify(sp.catch_exception(first_product.getTag()) == sp.Some("only the owner"))
    sc.verify(sp.catch_exception(second_product.getTag()) == sp.Some("only the owner"))
    sc.verify(sp.catch_exception(third_product.getTag()) == sp.Some("only the owner"))
