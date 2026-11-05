"""Decode a Dukascopy BID_candles_min_1.bi5 file (LZMA-compressed array of 24-byte records).
Record layout (big-endian): int32 time_offset_seconds, int32 open, int32 close, int32 low, int32 high, float32 volume.
Prices are integers scaled by 10^point_digits (EURUSD: 5, XAUUSD: 3)."""
import sys, lzma, struct
import numpy as np

def decode(path, scale):
    raw = open(path, 'rb').read()
    if len(raw) == 0:
        return np.zeros((0, 6))
    data = lzma.decompress(raw)
    n = len(data) // 24
    rec = np.frombuffer(data[:n*24], dtype=np.dtype('>i4,>i4,>i4,>i4,>i4,>f4'))
    out = np.empty((n, 6))
    out[:, 0] = rec['f0']
    out[:, 1] = rec['f1'] / scale  # open
    out[:, 2] = rec['f4'] / scale  # high
    out[:, 3] = rec['f3'] / scale  # low
    out[:, 4] = rec['f2'] / scale  # close
    out[:, 5] = rec['f5']
    return out

if __name__ == '__main__':
    path, scale = sys.argv[1], float(sys.argv[2])
    a = decode(path, scale)
    print('records', len(a))
    print('first 3 rows (sec, o, h, l, c, v):'); print(a[:3])
    print('last 3 rows:'); print(a[-3:])
    print('sec range', a[:,0].min() if len(a) else None, a[:,0].max() if len(a) else None)
    print('price range', a[:,3].min() if len(a) else None, a[:,2].max() if len(a) else None)
