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

if __name__ == "__main__":
    path = '/home/kali/src/Moclockingbird/assets/debug_connect-9dd9-common-x20-analog.csv'
    edges = detect_edges(path)
    plot(edges)
    # plot_interactive(edges)