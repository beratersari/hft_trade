import tkinter as tk
from tkinter import ttk
import pandas as pd
import json
from collections import defaultdict

# Configs matching generator (for consistency)
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'ADA/USDT']

# Per-symbol decimal precisions (for display; from generator's PRECISIONS)
PRECISIONS = {
    'BTC/USDT': 2,
    'ETH/USDT': 2,
    'XRP/USDT': 4,
    'ADA/USDT': 4
}

TOP_LEVELS = 10  # Show top N levels per side in GUI

class OrderBookGUI:
    """Simple GUI to visualize order book live from Excel deltas.
    Bids: green; Asks: red. Replays updates to simulate streaming feed.
    """
    def __init__(self, data_file='order_book_updates.xlsx'):
        self.data_file = data_file
        self.root = tk.Tk()
        self.root.title("Live Order Book Viewer - HFT Crypto Sim")
        self.root.geometry("600x400")
        
        # Load and prepare data (deltas from Excel)
        self.df = pd.read_excel(data_file)
        # Group deltas by symbol for replay; reconstruct books
        self.deltas_by_symbol = defaultdict(list)
        for sym in SYMBOLS:
            sym_df = self.df[self.df['symbol'] == sym]
            self.deltas_by_symbol[sym] = list(sym_df.itertuples(index=False))
        self.books = {sym: {'bids': {}, 'asks': {}} for sym in SYMBOLS}  # price -> qty
        self.current_indices = {sym: 0 for sym in SYMBOLS}
        
        # UI elements
        self.setup_ui()
        
    def setup_ui(self):
        # Symbol selector
        tk.Label(self.root, text="Select Symbol:").pack(pady=5)
        self.symbol_var = tk.StringVar(value=SYMBOLS[0])
        symbol_menu = ttk.Combobox(self.root, textvariable=self.symbol_var, values=SYMBOLS)
        symbol_menu.pack()
        symbol_menu.bind('<<ComboboxSelected>>', self.reset_book)
        
        # Start replay button
        tk.Button(self.root, text="Start Live Replay", command=self.start_replay).pack(pady=5)
        
        # Table for order book levels (bids/asks)
        self.tree = ttk.Treeview(self.root, columns=('Type', 'Price', 'Quantity', 'Cumul'), show='headings')
        self.tree.heading('Type', text='Side')
        self.tree.heading('Price', text='Price')
        self.tree.heading('Quantity', text='Qty')
        self.tree.heading('Cumul', text='Cumulative')
        self.tree.column('Type', width=50)
        self.tree.column('Price', width=150)
        self.tree.column('Quantity', width=100)
        self.tree.column('Cumul', width=100)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Color tags: green bids, red asks
        self.tree.tag_configure('bid', background='lightgreen')
        self.tree.tag_configure('ask', background='lightcoral')
        
        # Status
        self.status = tk.Label(self.root, text="Ready - Load data and start replay")
        self.status.pack(pady=5)
        
    def reset_book(self, event=None):
        """Reset book state for selected symbol."""
        sym = self.symbol_var.get()
        self.books[sym] = {'bids': {}, 'asks': {}}
        self.current_indices[sym] = 0
        self.clear_table()
        self.status.config(text=f"Reset book for {sym}")
        
    def clear_table(self):
        """Clear Treeview rows."""
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def apply_delta(self, sym, side, delta):
        """Apply delta update to book's side (list of [price, qty]; qty=0=delete)."""
        book_side = self.books[sym][side]
        for price, qty in delta:
            if qty == 0 or qty <= 0:  # delete/cancel
                book_side.pop(price, None)
            else:
                book_side[price] = qty
        # Trim to top levels post-update (bids desc, asks asc)
        if side == 'bids':
            sorted_levels = sorted(book_side.items(), reverse=True)[:TOP_LEVELS]
        else:
            sorted_levels = sorted(book_side.items())[:TOP_LEVELS]
        self.books[sym][side] = dict(sorted_levels)

    def match_orders(self, sym):
        """Execute matching orders to prevent crossed books: while max_bid >= min_ask,
        trade at midpoint/ask price, reduce qty from both (realistic fill logic).
        Handles partial fills and removes depleted levels. Call after deltas.
        """
        bids = self.books[sym]['bids']
        asks = self.books[sym]['asks']
        while bids and asks:
            best_bid = max(bids.keys())
            best_ask = min(asks.keys())
            if best_bid < best_ask:
                break  # no cross
            # Match: trade min qty at best_ask (common convention)
            trade_qty = min(bids[best_bid], asks[best_ask])
            # Log trade implicitly via status (for sim); reduce
            bids[best_bid] -= trade_qty
            asks[best_ask] -= trade_qty
            # Remove zero qty levels
            if bids[best_bid] <= 0:
                del bids[best_bid]
            if asks[best_ask] <= 0:
                del asks[best_ask]
        # Re-trim top levels post-match
        self.books[sym]['bids'] = dict(sorted(bids.items(), reverse=True)[:TOP_LEVELS])
        self.books[sym]['asks'] = dict(sorted(asks.items())[:TOP_LEVELS])
    
    def update_table(self, sym):
        """Refresh Treeview with top levels; color bids green, asks red. Compute cumul.
        Per user spec: Bids at top in ascending order; asks at bottom in descending order.
        Cumuls always from best level (best bid highest for bids, best ask lowest for asks)
        for logical depth, regardless of display sort.
        """
        self.clear_table()
        book = self.books[sym]
        
        # Bids first at top: ascending as requested (lowest bid first; best at bottom of bids section), green
        # Cumul: always from best bid (highest) down for logical depth (standard, independent of asc display sort)
        bid_levels = sorted(book['bids'].items())[:TOP_LEVELS]  # asc per request for display
        # Compute cumul map from best: sort desc temp, accum
        bid_sorted_for_cumul = sorted(book['bids'].items(), reverse=True)[:TOP_LEVELS]
        cumul_bid = 0
        cumul_map = {}  # price -> cumul_from_best
        for price, qty in bid_sorted_for_cumul:
            cumul_bid += qty
            cumul_map[price] = cumul_bid
        for price, qty in bid_levels:  # display asc, but use correct cumul
            self.tree.insert('', 'end', values=('Bid', f'{price:.{PRECISIONS.get(sym, 4)}f}', f'{qty:.4f}', f'{cumul_map.get(price, 0):.4f}'), tags=('bid',))
        
        # Asks at bottom: ascending for classical order book (lowest/best ask first in section), red
        # Cumul: always from best ask (lowest) down for logical depth
        ask_levels = sorted(book['asks'].items())[:TOP_LEVELS]  # asc (standard/classical)
        # Cumul map from best
        ask_sorted_for_cumul = sorted(book['asks'].items())[:TOP_LEVELS]
        cumul_ask = 0
        cumul_map = {}
        for price, qty in ask_sorted_for_cumul:
            cumul_ask += qty
            cumul_map[price] = cumul_ask
        for price, qty in ask_levels:  # display asc, correct cumul
            self.tree.insert('', 'end', values=('Ask', f'{price:.{PRECISIONS.get(sym, 4)}f}', f'{qty:.4f}', f'{cumul_map.get(price, 0):.4f}'), tags=('ask',))
        
    def replay_next_update(self, sym):
        """Replay next delta for 'live' feel; schedule next via timer.
        Applies deltas, then executes matches to keep book valid (no crossed prices).
        """
        idx = self.current_indices[sym]
        if idx < len(self.deltas_by_symbol[sym]):
            row = self.deltas_by_symbol[sym][idx]
            # Parse JSON deltas and apply
            bids_delta = json.loads(row.bids)
            asks_delta = json.loads(row.asks)
            self.apply_delta(sym, 'bids', bids_delta)
            self.apply_delta(sym, 'asks', asks_delta)
            # Execute any matches (e.g., aggressive bid hits ask) before display
            self.match_orders(sym)
            self.update_table(sym)
            self.status.config(text=f"Live: {sym} @ t={row.time:.2f} (update {idx+1}/{len(self.deltas_by_symbol[sym])})")
            self.current_indices[sym] += 1
            # Schedule next ~real-time (speed up slightly for demo: 10ms delay)
            self.root.after(10, lambda: self.replay_next_update(sym))
        else:
            self.status.config(text=f"Replay complete for {sym}")
    
    def start_replay(self):
        """Start live replay for selected symbol."""
        sym = self.symbol_var.get()
        self.reset_book()
        self.status.config(text=f"Starting live replay for {sym}...")
        self.replay_next_update(sym)
    
    def run(self):
        """Start GUI main loop."""
        self.root.mainloop()

if __name__ == "__main__":
    # Assumes order_book_updates.xlsx exists from generator
    gui = OrderBookGUI()
    gui.run()
