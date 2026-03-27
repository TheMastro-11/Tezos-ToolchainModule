from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from UpgradableProxy.UpgradeableProxyRosetta import *

@sp.add_test()
def testProxy():
    sc = sp.test_scenario("UpgradableProxy", [main, scenario_helpers])

    admin = sp.test_account("admin")
    outsider = sp.test_account("outsider")

    threshold = sp.mutez(100)
    below_threshold_logic = scenario_helpers.AcceptBelowThreshold(threshold)
    from_threshold_logic = scenario_helpers.AcceptFromThreshold(threshold)
    proxy = main.ProxyRosetta(admin.address, below_threshold_logic.address)
    caller = main.CallerRosetta()

    sc.h1("Main scenario")

    sc += below_threshold_logic
    sc += from_threshold_logic
    sc += proxy
    sc += caller

    sc.h2("Initial storage")
    sc.verify(proxy.data.admin == admin.address)
    sc.verify(proxy.data.logic_address == below_threshold_logic.address)

    sc.h2("Current implementation routing")
    proxy.check(sp.mutez(99), _sender=outsider.address)
    proxy.check(sp.mutez(100), _sender=outsider.address, _valid=False)
    caller.callLogicByProxy(proxy=proxy.address, balance=sp.mutez(99), _sender=outsider.address)
    caller.callLogicByProxy(proxy=proxy.address, balance=sp.mutez(100), _sender=outsider.address, _valid=False)

    sc.h2("Upgrade access control")
    proxy.upgradeTo(from_threshold_logic.address, _sender=outsider.address, _valid=False)
    sc.verify(proxy.data.logic_address == below_threshold_logic.address)

    sc.h2("Admin upgrade")
    proxy.upgradeTo(from_threshold_logic.address, _sender=admin.address)
    sc.verify(proxy.data.logic_address == from_threshold_logic.address)

    sc.h2("Updated implementation routing")
    proxy.check(sp.mutez(99), _sender=outsider.address, _valid=False)
    proxy.check(sp.mutez(100), _sender=outsider.address)
    caller.callLogicByProxy(proxy=proxy.address, balance=sp.mutez(99), _sender=outsider.address, _valid=False)
    caller.callLogicByProxy(proxy=proxy.address, balance=sp.mutez(100), _sender=outsider.address)
