import tkinter as tk
from tkinter import ttk
import pandas as pd
import json
import math  # for floor rounding (round down) per user request
from collections import defaultdict, OrderedDict

# Configs matching generator (for consistency)
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'XRP/USDT', 'ADA/USDT']

# Per-symbol decimal precisions (fallback/default for prices; from generator's PRECISIONS).
# Overridden by dynamic user price_precision_var in GUI for formatting/bucketing.
# All numbers (prices/qtys/cumuls) now rounded *down* (floor) to prec via helper.
# Qtys/cumuls floored for display (raw in storage).
PRECISIONS = {
    'BTC/USDT': 2,
    'ETH/USDT': 2,
    'XRP/USDT': 4,
    'ADA/USDT': 4
}

TOP_LEVELS = 10  # Show top N levels per side in GUI


def round_price_to_prec(value, prec, side):
    """Round price to specified decimal precision, directionally by side per latest
    mechanics: bids floor down (math.floor, conservative low), asks ceil up
    (math.ceil, conservative high). E.g., bid 64500.29@1->64500.2; ask 100.01@2->100.02.
    Handles positives for HFT orderbook. Uses factor math; avoids banker's round().
    Returns floored/ceiled float for bucketing/formatting.
    """
    if prec < 0:
        return value  # no-op for invalid
    factor = 10 ** prec
    if side == 'bids':
        return math.floor(value * factor) / factor  # round down bids
    else:  # asks
        return math.ceil(value * factor) / factor  # round up asks


def floor_to_prec(value, prec):
    """Round down (floor) a number to the specified decimal precision for qtys/cumuls
    (per 'all numbers' request). Uses math.floor; handles positives. Returns float.
    Separate from price rounding to keep qty fidelity in storage/agg.
    """
    if prec < 0:
        return value  # no-op for invalid
    factor = 10 ** prec
    return math.floor(value * factor) / factor


class OrderBookGUI:
    """Simple GUI to visualize order book live from Excel deltas for HFT crypto sim.
    - Bids: green (asc display); Asks: red (asc display).
    - Replays deltas for streaming feed; top 10 levels/side only (enforced in trims).
    - Per request: All numbers rounded *down* (floor via floor_to_prec) to prec for
      qtys/cumuls. Prices: *user-chosen* decimals (dynamic GUI selector; overrides
      PRECISIONS; side-specific bucketing/agg -- bids floor down, asks ceil up e.g.,
      bid 64500.29@1->64500.2, ask 100.01@2->100.02). Cumuls recalculated based on
      side-rounded prices. Dynamic change via UI without interrupting replay; qtys
      raw in storage.
    - NEW feature: Toggle to show only bids, only asks, or both (radio buttons; filters
      table in update_table).
    - Matches: prevents crossed books.
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
        # Use dict of OrderedDict for sides to maintain sorted order (bids desc, asks asc)
        # after trims in apply_delta/match_orders; enables sort-free viz in update_table.
        # Stores *raw* full-precision prices/qtys for accuracy. Price rounding/bucketing
        # + agg (for dups/cumuls based on formatted prices) is display-only in
        # update_table per dynamic user prec. Qtys always exact/raw (no change).
        # for HFT perf on large books/requests
        self.books = {
            sym: {'bids': OrderedDict(), 'asks': OrderedDict()} for sym in SYMBOLS
        }  # price -> qty, with order
        self.current_indices = {sym: 0 for sym in SYMBOLS}
        
        # UI elements
        self.setup_ui()
        
    def setup_ui(self):
        # Config for user-selectable *price* precision (decimals for formatting + bucketing;
        # overrides per-symbol PRECISIONS dict; dynamic GUI control as requested).
        # Bids floor down, asks ceil up per latest mechanics (conservative HFT display);
        # qtys/cumuls floor down. Default 2 for majors like BTC. Top 10 levels enforced
        # post-aggregation.
        self.PRECISION_OPTIONS = [0, 1, 2, 3, 4, 6, 8]
        
        # Symbol selector
        tk.Label(self.root, text="Select Symbol:").pack(pady=5)
        self.symbol_var = tk.StringVar(value=SYMBOLS[0])
        symbol_menu = ttk.Combobox(self.root, textvariable=self.symbol_var, values=SYMBOLS)
        symbol_menu.pack()
        symbol_menu.bind('<<ComboboxSelected>>', self.reset_book)
        
        # Price precision selector (dynamic user control for price formatting/bucketing)
        # Per request: user chooses # decimals; triggers table refresh for live update.
        # Bids round down, asks round up; cumuls re-calculated based on side-rounded prices.
        # Qtys remain floored raw.
        tk.Label(self.root, text="Price Precision (decimals):").pack(pady=5)
        self.price_precision_var = tk.StringVar(value='2')  # sensible default for price display
        precision_menu = ttk.Combobox(self.root, textvariable=self.price_precision_var, 
                                      values=[str(p) for p in self.PRECISION_OPTIONS])
        precision_menu.pack()
        precision_menu.bind('<<ComboboxSelected>>', self.change_precision)
        
        # NEW feature: View mode toggle for showing only bids, only asks, or both.
        # Radio buttons for simple user control; triggers filtered table refresh.
        # Default 'Both'; used in update_table filter.
        tk.Label(self.root, text="Show Orders:").pack(pady=5)
        self.view_mode_var = tk.StringVar(value='Both')
        for mode in ['Both', 'Bids Only', 'Asks Only']:
            tk.Radiobutton(self.root, text=mode, variable=self.view_mode_var, value=mode,
                           command=self.change_view).pack(anchor='w')
        
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
        """Reset book state for selected symbol. Uses empty OrderedDicts to maintain
        sorted order invariant with apply_delta/match_orders.
        """
        sym = self.symbol_var.get()
        self.books[sym] = {'bids': OrderedDict(), 'asks': OrderedDict()}
        self.current_indices[sym] = 0
        self.clear_table()
        self.status.config(text=f"Reset book for {sym}")
        
    def clear_table(self):
        """Clear Treeview rows."""
        for item in self.tree.get_children():
            self.tree.delete(item)
    
    def change_precision(self, event=None):
        """Hook for dynamic price precision change via GUI Combobox (<<ComboboxSelected>>).
        Per clarified request: allows user to change price decimal places on-the-fly (or
        via input equiv); refreshes table using current book state for selected symbol.
        Triggers price rounding + agg/bucketing (see update_table) and recalc of cumuls
        based on formatted prices. Qtys remain raw/unchanged. No full reset/replay
        restart needed, so live HFT sim continues. Top 10 levels post-agg.
        """
        sym = self.symbol_var.get()
        # Only refresh if book has data (populated via replay); status update always
        if self.books[sym]['bids'] or self.books[sym]['asks']:
            self.update_table(sym)
        self.status.config(text=f"Price prec set to {self.price_precision_var.get()} decimals for {sym}")
    
    def change_view(self):
        """NEW feature: Handle view mode toggle (Both/Bids Only/Asks Only) from radios.
        Filters table to show only selected orders; refreshes using current book state
        for symbol. Called on change; no reset/replay needed. Integrates with existing
        update_table (see mode filter there).
        """
        sym = self.symbol_var.get()
        # Only refresh if book has data; status update always
        if self.books[sym]['bids'] or self.books[sym]['asks']:
            self.update_table(sym)
        mode = self.view_mode_var.get()
        self.status.config(text=f"View mode: {mode} for {sym}")
    
    def apply_delta(self, sym, side, delta):
        """Apply delta update to book's side (list of [price, qty]; qty=0=delete).
        Stores raw full-precision prices/qtys in OrderedDict (sorted desc for bids,
        asc for asks post-trim). No rounding/bucketing here -- keeps data exact.
        Bucketing/rounding for prices happens only in viz (update_table) per user
        dynamic prec, to support aggregation for cumuls while qtys stay unchanged/raw.
        Trim to top levels; enables O(1) sorted access for HFT/large requests.
        """
        book_side = self.books[sym][side]
        for price, qty in delta:
            if qty == 0 or qty <= 0:  # delete/cancel
                book_side.pop(price, None)
            else:
                book_side[price] = qty
        # Trim to top levels post-update (bids desc, asks asc) and store as OrderedDict
        # to preserve sort order for downstream viz (see update_table). Raw values
        # preserved for accuracy (price rounding/agg is display-only).
        if side == 'bids':
            sorted_levels = sorted(book_side.items(), reverse=True)[:TOP_LEVELS]
        else:
            sorted_levels = sorted(book_side.items())[:TOP_LEVELS]
        self.books[sym][side] = OrderedDict(sorted_levels)

    def match_orders(self, sym):
        """Execute matching orders to prevent crossed books: while max_bid >= min_ask,
        trade at midpoint/ask price, reduce qty from both (realistic fill logic).
        Handles partial fills and removes depleted levels. Call after deltas.
        Uses raw prices/qtys for matching; post-trim OrderedDict for viz. No qty
        changes/rounding ever (per request). Bucketing only in display.
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
        # Re-trim top levels post-match; use OrderedDict to maintain sorted insertion
        # order (bids desc, asks asc) for viz efficiency. Raw values preserved --
        # price formatting/aggregation for cumuls is display-only (see update_table).
        self.books[sym]['bids'] = OrderedDict(sorted(bids.items(), reverse=True)[:TOP_LEVELS])
        self.books[sym]['asks'] = OrderedDict(sorted(asks.items())[:TOP_LEVELS])
    
    def update_table(self, sym):
        """Refresh Treeview with top levels (exactly TOP_LEVELS=10 per side); color bids
        green, asks red. Compute cumul.
        Per user spec/clarification: Bids at top in ascending order; asks at bottom in
        ascending order (preserved for classical depth display). Cumuls always from best
        level for logical depth, regardless of display sort.

        Prices rounded directionally by side (per latest mechanics): bids floor down,
        asks ceil up using round_price_to_prec (user-chosen prec via 'price_precision_var'
        selector; overrides PRECISIONS; e.g., bid 64500.29@1->64500.2, ask 100.01@2->100.02).
        Levels bucketed/aggregated by side-rounded price to avoid dups/clean HFT viz.
        Cumuls recalculated based on these (floored prices/qtys via floor_to_prec for
        'all numbers'). Qtys/cumuls floored down per fixed 4 dec for display+calc.
        Only top 10 levels post-agg. Optimized for HFT/large requests; dynamic refresh;
        books store raw floats.
        """
        self.clear_table()
        book = self.books[sym]
        
        # Get view mode for NEW filter feature (Both/Bids Only/Asks Only); skip
        # sections accordingly. Also get price prec etc.
        view_mode = self.view_mode_var.get()
        
        # Get user-chosen price precision (decimals) from GUI; int() safe as validated
        # options. Prices use side-specific round (bids down/asks up); qtys/cumuls use
        # floor_to_prec for all-numbers round down. Fixed 4 dec for qty/cumul.
        price_prec = int(self.price_precision_var.get())
        qty_display_prec = 4  # fixed; qty/cumul numbers floored down to this (display+calc)
        
        # Bids section: only if mode != 'Asks Only' (NEW filter feature).
        # Agg by *floored* price (round down via helper; bucketing for formatted
        # display; sum qtys to avoid dups post-floor). Sort desc for top/cumul from best,
        # asc for display. Enforce [:TOP_LEVELS] post-agg. Uses round_price_to_prec.
        # Raw qtys floored only for calc/display.
        if view_mode != 'Asks Only':
            raw_bids = book['bids']
            agg_bids = defaultdict(float)  # floored_price -> summed_qty (raw)
            for p, q in raw_bids.items():
                floor_p = round_price_to_prec(p, price_prec, 'bids')
                agg_bids[floor_p] += q
            bid_agg_desc = sorted(agg_bids.items(), reverse=True)[:TOP_LEVELS]
            bid_levels = list(reversed(bid_agg_desc))  # asc for display
            # Cumul map from best (desc agg; uses floored qtys -- round down per prec for
            # all numbers as requested; recalculated based on formatted/floored prices via
            # bucketing. Ensures displayed qty/cumul match floored values.)
            cumul_bid = 0
            cumul_map = {}  # floored_price -> cumul_from_best (floored qtys)
            for price, qty in bid_agg_desc:  # price already side-rounded (floor for bids)
                # Floor qty (raw value floored down to qty_display_prec for display+sum)
                floor_qty = floor_to_prec(qty, qty_display_prec)
                cumul_bid += floor_qty
                cumul_map[price] = cumul_bid
            for price, qty in bid_levels:  # display asc, correct cumul
                # Floor qty for display (all numbers rounded down; underlying raw preserved
                # only in book)
                floor_qty = floor_to_prec(qty, qty_display_prec)
                self.tree.insert('', 'end', values=(
                    'Bid',
                    f'{price:.{price_prec}f}',  # formatted floored price (bids down)
                    f'{floor_qty:.{qty_display_prec}f}',  # floored qty display (down per prec)
                    f'{cumul_map.get(price, 0):.{qty_display_prec}f}'  # floored cumul
                ), tags=('bid',))
        
        # Asks section: only if mode != 'Bids Only' (NEW filter feature).
        # Agg by *ceiled* price (round up via helper; asc sort; bucketing for
        # clean display). Use directly for display/cumul from best (lowest). Enforce
        # top [:TOP_LEVELS] post-agg. Qtys/cumuls floored down; cumuls based on
        # side-rounded prices. Note: asc preserved for classical.
        if view_mode != 'Bids Only':
            raw_asks = book['asks']
            agg_asks = defaultdict(float)
            for p, q in raw_asks.items():
                ceil_p = round_price_to_prec(p, price_prec, 'asks')
                agg_asks[ceil_p] += q
            ask_agg_asc = sorted(agg_asks.items())[:TOP_LEVELS]  # asc
            # Cumul map from best (reuse agg list; floored qtys)
            cumul_ask = 0
            cumul_map = {}
            for price, qty in ask_agg_asc:
                # Floor qty for sum/display (round down all numbers per prec)
                floor_qty = floor_to_prec(qty, qty_display_prec)
                cumul_ask += floor_qty
                cumul_map[price] = cumul_ask
            for price, qty in ask_agg_asc:  # display asc, correct cumul
                floor_qty = floor_to_prec(qty, qty_display_prec)
                self.tree.insert('', 'end', values=(
                    'Ask',
                    f'{price:.{price_prec}f}',  # formatted ceiled price (asks up)
                    f'{floor_qty:.{qty_display_prec}f}',  # floored qty display
                    f'{cumul_map.get(price, 0):.{qty_display_prec}f}'  # floored cumul
                ), tags=('ask',))
        
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
