import plotly.graph_objects as go

BAUD_RATE = 115200
bit_time  = 1 / BAUD_RATE

# # Digital data (timestamp, byte, direction)
# data_points = [
#     (16.627122092, 0x01, True),
#     (16.657150092, 58,   True),
#     (16.657576092, 1,    True),
#     (16.657688092, 3,    True),
#     (16.657800092, 154,  True),
#     (16.657914092, 0,    True),
#     (16.658026092, 18,   True),
#     (16.658138092, 81,   True),
#     (16.658252092, 3,    True),
#     (16.661292092, 2,    False),
# ]
# 
def load_data():
    data_points = []
    import ast
    with open("/home/kali/src/Moclockingbird/assets/digests.json") as f:
        data_points = [
            ast.literal_eval(
                line.strip()
                    .replace("{", "(")
                    .replace("}", ")")
                    .replace("),", ")")
                    .replace("true", "True")
                    .replace("false", "False")
            )
            for line in f
            if line.strip() # process non-empty line only
        ]
    return data_points

data_points = load_data()

print(data_points)
# — Frame detector as a tiny state machine —
def detect_frames(data_points):
    """
    [(time, hex, direction),...]
    """
    START_MAP = {0x01: 'CMD', 0x02: 'DATA'}
    END_MARK  = 0x03
    STATE_IDLE, STATE_LEN, STATE_DATA, STATE_SUM, STATE_END = range(5)

    frames = []

    def reset_states():
        return STATE_IDLE, {}

    state, frame  = reset_states()

    tPrev = 0
    dirPrev = False
    sameFrameTolerance = (1 / BAUD_RATE) * (10 * 10) # after which probably not same frame
    
    for idx, (t, b, direction) in enumerate(data_points):
        if t - tPrev > sameFrameTolerance or direction != dirPrev:
            state, frame  = reset_states()
            tPrev = t
            dirPrev = direction
            # then proceed to STATE_IDLE

        if state == STATE_IDLE:
            if b in START_MAP:
                frame = {'START': b, 'type': START_MAP[b], 'startIdx': idx, 'data': []}
                state = STATE_LEN
                tPrev = t
                dirPrev = direction
        elif state == STATE_LEN:
            frame['LEN'] = b
            state = STATE_DATA if b > 0 else STATE_SUM
            tPrev = t
            dirPrev = direction
        elif state == STATE_DATA:
            frame['data'].append(b)
            if len(frame['data']) == frame['LEN']:
                state = STATE_SUM
            tPrev = t
            dirPrev = direction
        elif state == STATE_SUM: # checksum, sum(Frame[1:SUM]) & 0xFF == 0
            frame['SUM'] = b
            state = STATE_END
            tPrev = t
            dirPrev = direction
        elif state == STATE_END:
            frame['endIdx'] = idx
            good_end = (b == END_MARK)
            good_ck  = (((frame['LEN'] + sum(frame['data']) + frame['SUM']) & 0xFF) == 0)
            if good_end and good_ck:
                frames.append(frame)
            state, frame = reset_states()

    return frames

# — Prepare raw byte list & detect frames —
# raw_bytes = [byte for _, byte, _ in data_points]
frames    = detect_frames(data_points)

# — Build waveform & annotations —

# times, values = [], []
# mid_times, labels = [], []
# 
# for tByteStart, byte, _ in data_points:
#     bits = [0] + [(byte >> i) & 1 for i in range(8)] + [1] # LSB, 1+8N1
#     for i, bit in enumerate(bits):
#         tBitStart = tByteStart + i * bit_time
#         tBitEnd = tByteStart + (i + 1) * bit_time
#         times.extend([tBitStart, tBitEnd]); values.extend([bit, bit])
#     mid_times.append(tByteStart + (1 + 4) * bit_time)
#     labels.append(f"{byte:02X}")

# — Plot —
fig = go.Figure()

# the "Signal"
# Prepare containers
times_fwd,  values_fwd  = [], []
times_rev,  values_rev  = [], []
mid_times,  labels      = [], []

# ─────────────────────────────────────────────────────────────────────────────
# Build bit‑level forward/reverse series
# ─────────────────────────────────────────────────────────────────────────────
for t_byte, byte, direction in data_points:
    bits = [0] + [(byte >> i) & 1 for i in range(8)] + [1] # LSB, 1+8N1
    for i, bit in enumerate(bits):
        tBitStart = t_byte + i * bit_time
        tBitEnd = t_byte + (i + 1) * bit_time
        if direction:
            # forward segment
            times_fwd.extend([tBitStart, tBitEnd])
            values_fwd.extend([bit, bit])
            # break in reverse
            times_rev.extend([None, None])
            values_rev.extend([None, None])
        else:
            # reverse segment
            times_rev.extend([tBitStart, tBitEnd])
            values_rev.extend([bit, bit])
            # break in forward
            times_fwd.extend([None, None])
            values_fwd.extend([None, None])
    # compute label position (mid‐byte) and text
    mid = t_byte + (1 + 4) * bit_time
    mid_times.append(mid)
    labels.append(f"{byte:02X}")


# — forward‐direction trace (e.g. blue) —
fig.add_trace(go.Scatter(
    x=times_fwd, y=values_fwd,
    mode='lines',
    line_shape='hv',
    name='Signal (forward)',
    line_color='LightSkyBlue'
))

# — reverse‐direction trace (red) —
fig.add_trace(go.Scatter(
    x=times_rev, y=values_rev,
    mode='lines',
    line_shape='hv',
    name='Signal (reverse)',
    line_color='red'
))


# fig.add_trace(go.Scatter(
#     x=times, y=values,
#     mode='lines', line_shape='hv', name='Signal'
# ))
fig.add_trace(go.Scatter(
    x=mid_times, y=[1.0000001]*len(labels),
    mode='text', text=labels,
    textposition='top center', name='Bytes'
))

# — Shade each detected frame —
for frame in frames:
    startPacketIdx = frame['startIdx']
    endPacketIdx = frame['endIdx']
    fType = frame['type']
    tByteStart = data_points[startPacketIdx][0]
    t_end   = data_points[endPacketIdx][0] + (1 + 8 + 1) * bit_time
    fig.add_vrect(
        x0=tByteStart, x1=t_end,
        fillcolor='LightSalmon' if fType=='CMD' else 'LightSkyBlue',
        opacity=0.3, layer='below',
        annotation_text=fType, annotation_position='top left'
    )

# — Final layout tweaks —
fig.update_yaxes(range=[-0.1, 1.02], title='Signal Level')
fig.update_xaxes(title='Time (s)')
fig.update_layout(
    title=f"Serial Decode @ {BAUD_RATE} baud — CMD vs DATA Frames",
    hovermode='x unified'
)

fig.show()
