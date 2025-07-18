#!/usr/bin/python3

import csv
from typing import Dict, List, Tuple

TH_LOW = 0.3    # 0 ≤ V < 0.3 → L
TH_HIGH = 1.2   # 0.3 ≤ V < 1.2 → M,  V ≥ 1.2 → H
def analog_to_level(voltage: float) -> str:
    """
    Map a single analog voltage to a digital level:
      0.0–0.3 → 'L'
      0.3–1.2 → 'M'
      1.2+   → 'H'
    """
    if voltage < TH_LOW:
        return 'L'
    elif voltage < TH_HIGH:
        return 'M'
    else:
        return 'H'

def detect_edges(path: str) -> Dict[str, List[Tuple[float, str]]]:
    """
    Read CSV line by line, detect when each channel's level changes,
    collect the (timestamp, new_level) of
      - the datapoint of the level change
      - the datapoint just before the level change
    """
    edges = {
        'dbg-data': [],
        'TB-data': []
    }
    last_levels: Dict[str, str]     = { c: None for c in edges } # {'TB-data': None, 'dbg-data': None}
    last_times: Dict[str, float]    = { c: None for c in edges }
    with open(path, newline='') as fp:
        reader = csv.DictReader(fp)
        # prev_levels = {'TB-data': None, 'dbg-data': None}
        for row in reader:
            t = float(row['Time [s]'])
            for chan in edges:
                lvl = analog_to_level(float(row[chan]))
                prev_level = last_levels[chan]
                prev_time  = last_times[chan]
                if prev_level is None:
                    # The first datapoint: record the (timestamp,level) as is
                    edges[chan].append((t, lvl))
                elif lvl != prev_level:
                    # level changed: record both the previous (if not recorded) and current time
                    last_registered_time =  edges[chan][-1][0] # last_registered_level =  edges[chan][-1][1]
                    if last_registered_time != prev_time:
                        edges[chan].append((prev_time, prev_level))
                    edges[chan].append((t, lvl))
                # update trackers for *next* iteration
                last_levels[chan] = lvl
                last_times[chan]  = t
    # add the last datapoint if not already added
    for chan in edges:
        last_registered_time =  edges[chan][-1][0] # last_registered_level =  edges[chan][-1][1]
        last_level = last_levels[chan]
        last_time  = last_times[chan]
        if last_registered_time != last_time:
            edges[chan].append((last_time, last_level))
    return edges

def plot(edges: Dict[str, List[Tuple[float, str]]]):
    import matplotlib.pyplot as plt
    # edges = {
    #     'TB-data': [(t0, 'L'), (t1, 'M'), (t2, 'L'), …],
    #     'dbg-data': [(t0, 'L'), (t3, 'H'), …]
    # }
    # Y axis
    level_map = {'L': 0, 'M': 1, 'H': 2}
    plt.figure()
    for chan, evts in edges.items():
        # Unzip timestamps and levels
        times, levels_text = zip(*evts)
        # Convert levels to numbers
        levels = [level_map[l] for l in levels_text]
        # Draw a step plot, holding the new level until the next timestamp
        plt.step(times, levels, where='post', label=chan)
    # Label the y‑axis with the original level names
    plt.yticks([0, 1, 2], ['L', 'M', 'H'])
    # t_min, t_max = 69.18, 69.185
    # t_min, t_max = 35, 69.185
    t_min, t_max = 40.90, 41.18
    plt.xlim(t_min, t_max)
    plt.xlabel('Time [s]')
    plt.ylabel('Digital Level')
    plt.title('Edge Transitions')
    plt.legend()
    plt.tight_layout()
    plt.show()

def plot_interactive(edges: Dict[str, List[Tuple[float, str]]]):
    import pandas as pd
    import plotly.express as px
    # edges = {
    #     'TB-data': [(t0, 'L'), (t1, 'M'), (t2, 'L'), …],
    #     'dbg-data': [(t0, 'L'), (t3, 'H'), …]
    # }
    # Y axis
    level_map = {'L': 0, 'M': 1, 'H': 2}
    # Flatten into a DataFrame
    records = []
    for chan, evts in edges.items():
        for t, l in evts:
            records.append({'Time [s]': t, 'Level': level_map[l], 'Channel': chan})
    df = pd.DataFrame(records)
    # Interactive plot
    fig = px.line(
        df,
        x='Time [s]',
        y='Level',
        color='Channel',
        line_shape='hv',      # horizontal‑vertical steps
        labels={'Level': 'Digital Level'},
        category_orders={'Channel': ['dbg-data', 'TB-data']}
    )
    fig.update_yaxes(tickmode='array', tickvals=[0, 1, 2], ticktext=['L', 'M', 'H'])
    fig.update_layout(title=f'Edge Transitions')
    fig.show()


_times_cache = {}
_levels_cache = {}
def _build_caches(edges):
    for chan, evts in edges.items():
        _times_cache[chan]  = [ts  for ts, _ in evts]
        _levels_cache[chan] = [lvl for _, lvl in evts]

def get_level_at(edges, chan, t_query):
    """
    Get the level at t
    Assume initial level is always High
    """
    import bisect
    # Build caches on first call
    if chan not in _times_cache:
        _build_caches(edges)
    times  = _times_cache[chan]
    levels = _levels_cache[chan]
    idx = bisect.bisect_right(times, t_query) - 1 # [1, 2, 3], 2.1 => idx == 1 (the level of "t==2")
    return levels[idx] if idx >= 0 else 'H'
#     lv_query = 'H'
#     idx = bisect.bisect_right(times, t_query) - 1
#     for t, lv in edges[chan]:
#         if t <= t_query:
#             lv_query = lv
#         else:
#             break
#     return lv_query

def bits_to_byte(bits):
    """
    Convert an array of 8 bits (LSB first) into one byte.
    IN: bits: [b0, b1, …, b7] where b0 is least significant bit.
    OUT: one byte
    """
    b = sum(bit << idx for idx, bit in enumerate(bits))
    return b

def convert_to_digital(edges: Dict[str, List[Tuple[float, str]]], chan_dbg, chan_board, data_bits=8, stop_bits=1):
    """
    Decode all 8N1 (or 8N2 if stop_bits=2) frames on `chan`.
    Returns a list of (start_time, [direction_bit, b0, b1,…, b7]) tuples.
    """
    BAUD_RATE   = 115200
    BIT_PERIOD  = 1.0 / BAUD_RATE  # seconds per bit
    frames    = []
    prev_lvl  = None
    t0 = 0
    for t_edge, lvl in edges[chan_dbg]:
        if not prev_lvl:
            if lvl != 'H': # (Spec: Idle is always High)
                continue
            prev_lvl = lvl
            continue
        if t_edge < t0: # Avoid parsing inside a "packet"
            continue
        # Detect the falling edge (idle=H → start=low) (Spec: the start of signal is 1 low bit)
        # Under the if: one "packet" (1 byte)
        if prev_lvl == 'H' and lvl != 'H':
            t0 = t_edge # t0 is where the level change
            # extract 8 data bits
            bits = []
            is_from_dbg_to_board = None # None is unknown
            for i in range(data_bits):
                # sample in the middle of each bit:
                t_query = t0 + BIT_PERIOD * (1 + i + 0.5)
                lvl_chan_dbg = get_level_at(edges, chan_dbg, t_query)
                lvl_chan_board = get_level_at(edges, chan_board, t_query)
                bit = (1 if lvl_chan_dbg == 'H' else 0)
                bits.append(bit)
                if bit == 0: # since the spec says the first bit is always low, the branch always hits
                    if lvl_chan_board == 'M': # dbg will never be 'M' (in our cases)
                        is_from_dbg_to_board = True
                    else:
                        is_from_dbg_to_board = False
                b = bits_to_byte(bits)
            frames.append((t0, b, is_from_dbg_to_board))
            if is_from_dbg_to_board: # (Spec: 1 + 8N2)
                t0 += BIT_PERIOD * (1 + 8 + 2)
            else: # (Spec: 1 + 8N1)
                t0 += BIT_PERIOD * (1 + 8 + 1)
        prev_lvl = lvl
    return frames

if __name__ == "__main__":
    path = '/home/kali/src/Moclockingbird/assets/debug_connect-9dd9-common-x20-analog.csv'
    edges = detect_edges(path)
    frames = convert_to_digital(edges, 'dbg-data', 'TB-data', data_bits=8)
    print(frames)
    plot(edges)
    # plot_interactive(edges)