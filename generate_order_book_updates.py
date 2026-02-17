import time
import random
import json
import pandas as pd

# Trading pairs
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'ADA/USDT']

# Initial base prices per symbol for realistic starting points
INITIAL_BASE_PRICES = {
    'BTC/USDT': 65000.0,
    'ETH/USDT': 3500.0,
    'XRP/USDT': 0.75,
    'ADA/USDT': 0.45
}

# Symbol-specific volatility for random walk (smaller for major pairs to avoid price jumps; % change per update)
VOLATILITIES = {
    'BTC/USDT': 0.00001,  # ~0.65 USD steps
    'ETH/USDT': 0.00005,  # ~0.175 USD steps
    'XRP/USDT': 0.0005,   # ~0.000375 USD steps
    'ADA/USDT': 0.0005    # ~0.000225 USD steps
}

# Per-symbol tick sizes (min price increment; logical for each pair's scale/liquidity)
TICK_SIZES = {
    'BTC/USDT': 0.01,   # Common for high-value majors
    'ETH/USDT': 0.01,   # Similar to BTC
    'XRP/USDT': 0.0001, # For low-value pairs
    'ADA/USDT': 0.0001  # For low-value pairs
}

# Decimal precision for rounding prices per symbol (BTC/ETH: 2 decimals; XRP/ADA: 4+ for finer granularity)
PRECISIONS = {
    'BTC/USDT': 2,
    'ETH/USDT': 2,
    'XRP/USDT': 4,
    'ADA/USDT': 4
}

# Max levels to maintain in the order book per side (prevents infinite growth)
MAX_LEVELS = 20

# Helper: Initialize a full order book for a symbol
def init_order_book(base_price, symbol):
    """Create initial bid/ask dicts: price -> quantity (for easy updates).
    Uses symbol-specific tick size and precision for realistic scaling/granularity.
    """
    bids = {}  # price -> qty, will keep sorted desc
    asks = {}  # price -> qty, sorted asc
    tick = TICK_SIZES[symbol]
    prec = PRECISIONS[symbol]
    # Generate initial levels around base using relative offsets (tick multiples)
    for i in range(MAX_LEVELS):
        # Bids: below base (relative offset)
        bid_offset = (i + 1) * tick * random.uniform(1, 2)
        bid_price = round(base_price - bid_offset, prec)
        bids[bid_price] = round(random.uniform(0.1, 10.0), 4)
        # Asks: above base (relative)
        ask_offset = (i + 1) * tick * random.uniform(1, 2)
        ask_price = round(base_price + ask_offset, prec)
        asks[ask_price] = round(random.uniform(0.1, 10.0), 4)
    return bids, asks

# Helper: Apply random delta update to book (add/modify/delete) for realism
def apply_order_book_delta(book, mid_price, symbol, side='bid'):
    """Randomly update 1-3 levels: modify qty, add new level, or delete (cancel).
    Offsets are relative (%/tick-based) to mid_price and symbol's scale; uses
    per-symbol tick/precision (e.g., BTC: 0.01 tick/2 dec; XRP: 0.0001/4 dec).
    Ensures bids < mid < asks, no cross or jumps. qty=0 means delete.
    Returns sorted delta list of [price, qty].
    """
    delta = []
    num_changes = random.randint(1, 3)
    tick = TICK_SIZES[symbol]
    prec = PRECISIONS[symbol]
    for _ in range(num_changes):
        # Relative micro-offset (tick multiples) for continuity + pair-specific scaling
        offset = random.uniform(0.5, 5) * tick  # e.g., 0.005-0.05 for BTC, much smaller % for XRP
        if side == 'bid':
            # Bid: strictly below mid
            price = round(mid_price - offset, prec)
        else:
            # Ask: strictly above mid
            price = round(mid_price + offset, prec)
        
        action = random.choice(['modify', 'add', 'delete'])
        if action == 'delete' or (random.random() < 0.2 and price in book):  # higher delete chance for bounded size
            # Delete/cancel: qty=0 in delta
            if price in book:
                del book[price]
            delta.append([price, 0.0])
        else:
            # Add or modify: random qty (can be at existing for modify)
            qty = round(random.uniform(0.1, 10.0), 4)
            book[price] = qty
            delta.append([price, qty])
    
    # Trim book to MAX_LEVELS, remove extremes to keep bounded
    if len(book) > MAX_LEVELS:
        prices = sorted(book.keys(), reverse=(side == 'bid'))
        for p in prices[MAX_LEVELS:]:
            del book[p]
    
    # Dedup/sort delta for output: bids desc, asks asc; ensures no unrealistic jumps
    delta = list({p: q for p, q in delta}.items())  # dedup same-price
    delta.sort(key=lambda x: x[0], reverse=(side == 'bid'))
    return delta

# Helper to update mid-price via random walk for price continuity (no jumps)
def update_mid_price(current_price, symbol):
    """Symbol-specific small random walk step to simulate realistic price movement without jumps.
    Volatility (%-based) + tick/precision ensure logical scaling (e.g., BTC 2-dec vs. XRP 4-dec).
    """
    volatility = VOLATILITIES.get(symbol, 0.0001)
    prec = PRECISIONS[symbol]
    step = current_price * random.uniform(-volatility, volatility)
    # Round to nearest tick for precision
    tick = TICK_SIZES[symbol]
    rounded = round(current_price + step, prec)
    return round(rounded / tick) * tick  # snap to tick grid

# Helper: Get update portion (deltas only) from current book
def get_order_book_updates(bids, asks, mid_price, symbol):
    """For each update event, generate bid/ask deltas separately using current mid-price.
    Passes symbol for tick/precision config. Deltas ensure updates are additive only
    where changed, with deletes for bounded book.
    """
    bid_delta = apply_order_book_delta(bids, mid_price, symbol, 'bid') if bids else []
    ask_delta = apply_order_book_delta(asks, mid_price, symbol, 'ask') if asks else []
    return bid_delta, ask_delta

# Main generator function
def generate_order_book_updates(duration=10, output_file='order_book_updates.xlsx'):
    """
    Generates mock order book update data over a specified duration and saves to Excel.
    Now uses persistent per-symbol order books with delta updates (add/modify/delete)
    to keep book size bounded (~20 levels/side) and prevent growth. Updates are only
    the changed portions, as received from real APIs.
    
    :param duration: Duration in seconds to stream data (default 10)
    :param output_file: Path to save the Excel file
    """
    data = []
    start_time = time.time()
    end_time = start_time + duration
    
    # Maintain persistent order books and mid-prices per symbol for realism
    order_books = {}
    mid_prices = {}
    for sym in SYMBOLS:
        base_price = INITIAL_BASE_PRICES[sym]
        # Init with symbol-specific tick/precision
        bids, asks = init_order_book(base_price, sym)
        order_books[sym] = {'bids': bids, 'asks': asks}
        mid_prices[sym] = base_price
    
    print(f"Starting realistic order book update generation for {duration} seconds...")
    
    while time.time() < end_time:
        # Current timestamp as float (Unix epoch)
        timestamp = time.time()
        
        # Random symbol (can have multiple updates per symbol over time)
        symbol = random.choice(SYMBOLS)
        
        # Update mid-price with symbol-specific random walk for continuity (avoids jumps)
        mid_prices[symbol] = update_mid_price(mid_prices[symbol], symbol)
        mid_price = mid_prices[symbol]
        
        # Get book for symbol and generate deltas (updates only; includes qty=0 for deletes)
        # Pass symbol for tick/precision scaling
        book = order_books[symbol]
        bids_delta, asks_delta = get_order_book_updates(book['bids'], book['asks'], mid_price, symbol)
        
        # Store deltas as JSON strings for Excel compatibility
        # Bids: descending price; Asks: ascending; partial updates only
        record = {
            'time': timestamp,
            'symbol': symbol,
            'bids': json.dumps(bids_delta),  # e.g., [[price, qty], ...] or qty=0 for cancel
            'asks': json.dumps(asks_delta)   # e.g., [[price, qty], ...]
        }
        data.append(record)
        
        # Higher frequency for crypto/HFT sim: ~100-1000 updates/sec
        time.sleep(random.uniform(0.001, 0.01))
    
    # Convert to DataFrame and save to Excel
    df = pd.DataFrame(data)
    df.to_excel(output_file, index=False, engine='openpyxl')
    
    print(f"Generated {len(data)} updates. Data saved to {output_file}")
    return output_file

if __name__ == "__main__":
    generate_order_book_updates()
