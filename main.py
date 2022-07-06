from enum import Enum
from typing import Optional, List

import pydantic
from collections import deque, defaultdict


class Side(Enum):
    BUY = -1  # Buyers bid, cash goes down
    SELL = 1  # Sellers sell, cash goes up


class Order(pydantic.BaseModel):
    id: int
    side: Side
    quantity: int
    price: int


class Trade(pydantic.BaseModel):
    buyer: int
    seller: int
    price: int
    quantity: int

    def __str__(self):
        return f"Trade[seller={self.seller} => buyer={self.buyer}] #{self.quantity} at ${self.price}"


class OrderLevel:
    def __init__(self):
        self.orders = deque()

    def add(self, order: Order):
        self.orders.append(order)

    def execute_sell(self, seller: int, at_price: int, total_quantity: int) -> (List[Trade], int):
        # We don't match on price, that has been done before
        trades = []
        # Oldest to most recent
        while self.orders:
            order = self.orders[0]
            if total_quantity < order.quantity:
                # we finish the trade
                trades.append(Trade(seller=seller, buyer=order.id, price=at_price, quantity=total_quantity))
                order.quantity -= total_quantity
                total_quantity == 0
                break
            else:
                # We execute all and continue
                trades.append(Trade(seller=seller, buyer=order.id, price=at_price, quantity=order.quantity))
                total_quantity -= order.quantity
                self.orders.popleft()
        return trades, total_quantity

    def depth(self):
        return sum((order.quantity for order in self.orders))


class OrderBook:
    def __init__(self):
        self.bids = defaultdict(OrderLevel)
        self.asks = defaultdict(OrderLevel)

    def calc_max_bid(self):
        return max(self.bids.keys()) if self.bids else float('-inf')

    def calc_min_ask(self):
        return min(self.asks.keys()) if self.asks else float('inf')

    def spread(self, side: Side) -> (Optional[int], Optional[int]):
        return (self.calc_min_ask(), None) if side == Side.BUY else (None, self.calc_max_bid())

    def execute_sell(self, order: Order) -> (List[Trade], int):
        levels = sorted([price for price, level in self.bids.items() if price >= order.price], reverse=True)
        total_quantity = order.quantity
        executed_trades = []
        for price in levels:
            level = self.bids[price]
            trades, total_quantity = level.execute_sell(order.id, price, total_quantity)
            executed_trades += trades
            if not level.orders:
                del self.bids[price]
            if total_quantity == 0:
                # We have executed everything
                break
        return executed_trades, total_quantity

    def process(self, order: Order) -> List[Trade]:
        min_ask, max_bid = self.spread(order.side)
        match order.side, order.price:
            case Side.BUY, price if price >= min_ask:
                print("Execute BUY")
            case Side.BUY, price if price < min_ask:
                self.bids[price].add(order)
                return []
            case Side.SELL, price if price <= max_bid:
                print(f"Execute SELL at ${price} of quantity {order.quantity}")
                trades, quantity_left = self.execute_sell(order)
                if quantity_left == 0:
                    print("we sold everything")
                    order.quantity = quantity_left
                    self.asks[order.price].add(order)
                return trades

            case Side.SELL, price if price > max_bid:
                self.asks[price].add(order)
                return []
            case _:
                raise "Impossible"


class Output:
    def __init__(self):
        self.spaces = 10

    def print(self, book: OrderBook):
        bids = [self.format(price, level) for price, level in sorted(book.bids.items(), reverse=True)]
        asks = [self.format(price, level) for price, level in sorted(book.asks.items())]
        self.outline(bids, asks)

    def outline(self, bids: List[str], asks: List[str]):

        length_bids = max((len(s) for s in bids)) + self.spaces
        length_asks = max((len(s) for s in asks)) + self.spaces

        def draw_line(sep):
            print('_' * length_bids + '_' + sep + '_' * length_asks)

        if len(bids) > len(asks):
            asks += ['' for _ in range(len(bids) - len(asks))]
        elif len(asks) > len(bids):
            bids += ['' for _ in range(len(asks) - len(bids))]
        draw_line('_')
        print(f"{'BID (Buyers)'.ljust(length_bids)} | ASK (Sellers)")
        draw_line('|')

        for bid, ask in zip(bids, asks):
            print(f"{bid.ljust(length_bids)} | {ask}")
        draw_line('|')

    def format(self, price: int, level: OrderLevel) -> str:
        return f"Level {price}: Total {level.depth()} / #{len(level.orders)} order"


if __name__ == '__main__':
    book = OrderBook()
    orders = [Order(id=1, side=Side.BUY, price=100, quantity=1),
              Order(id=2, side=Side.BUY, price=100, quantity=2),
              Order(id=3, side=Side.BUY, price=99, quantity=1),
              Order(id=4, side=Side.BUY, price=99, quantity=2),
              Order(id=5, side=Side.BUY, price=99, quantity=3),
              Order(id=6, side=Side.BUY, price=98, quantity=3),
              Order(id=7, side=Side.SELL, price=101, quantity=3),
              Order(id=8, side=Side.SELL, price=102, quantity=5)]
    for o in orders:
        book.process(o)

    output = Output()
    output.print(book)

    print("Doing a fire sale")
    executed_sale = Order(id=9, side=Side.SELL, price=99, quantity=5)
    executed_trades = book.process(executed_sale)

    for t in executed_trades:
        print(t)

    output.print(book)
