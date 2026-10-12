"""Order-planning tests (pure function)."""

from __future__ import annotations

from src.execution.orders import plan_orders


def test_plan_buy_and_sell():
    planned = plan_orders(
        {"BTC/USDT": 0.5, "ETH/USDT": 0.0},
        equity=10_000.0,
        current_qty={"ETH/USDT": 5.0},
        prices={"BTC/USDT": 100.0, "ETH/USDT": 50.0},
    )
    by_symbol = {order.symbol: order for order in planned}
    assert by_symbol["BTC/USDT"].side == "buy"
    assert by_symbol["BTC/USDT"].qty == 50.0  # 0.5 * 10000 / 100
    assert by_symbol["ETH/USDT"].side == "sell"
    assert by_symbol["ETH/USDT"].qty == 5.0


def test_no_order_below_min_notional():
    assert plan_orders({"BTC/USDT": 0.000001}, 10_000.0, {}, {"BTC/USDT": 100.0}) == []


def test_missing_price_is_skipped():
    assert plan_orders({"BTC/USDT": 0.5}, 10_000.0, {}, {}) == []


def test_rebalance_within_tolerance_is_skipped():
    # currently 50 units of a $100 asset = $5000 = 50% of equity; target 50%.
    planned = plan_orders({"BTC/USDT": 0.5}, 10_000.0, {"BTC/USDT": 50.0}, {"BTC/USDT": 100.0})
    assert planned == []
