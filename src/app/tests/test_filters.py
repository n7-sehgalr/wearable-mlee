import sys
import os
import math
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from src.interfaces.desktop.filters import StreamingEMA, StreamingMA, compute_autoscale_range

def test_ema_first_sample_equals_input():
    ema = StreamingEMA(cutoff_hz=1.0, sample_rate_hz=100.0)
    assert ema.value is None
    res = ema.update(42.0)
    assert res == 42.0
    assert ema.value == 42.0

def test_ema_convergence():
    ema = StreamingEMA(cutoff_hz=1.0, sample_rate_hz=100.0)
    ema.update(0.0)
    for _ in range(100):
        ema.update(100.0)
    # With alpha ~0.06, 100 samples should get it very close to 100
    assert 99.0 < ema.value <= 100.0

def test_ema_nan_handling():
    ema = StreamingEMA()
    ema.update(10.0)
    res = ema.update(float('nan'))
    assert res == 10.0
    assert ema.value == 10.0

def test_ema_inf_handling():
    ema = StreamingEMA()
    ema.update(20.0)
    res = ema.update(float('inf'))
    assert res == 20.0
    assert ema.value == 20.0

def test_ema_reset():
    ema = StreamingEMA()
    ema.update(50.0)
    ema.reset()
    assert ema.value is None
    res = ema.update(100.0)
    assert res == 100.0

def test_ma_startup_few_samples():
    ma = StreamingMA(window=5)
    assert ma.value is None
    res1 = ma.update(10.0)
    assert res1 == 10.0
    res2 = ma.update(20.0)
    assert res2 == 15.0

def test_ma_full_window():
    ma = StreamingMA(window=3)
    ma.update(10.0)
    ma.update(20.0)
    ma.update(30.0)
    assert ma.value == 20.0
    # Add another, dropping the 10
    ma.update(40.0)
    assert ma.value == 30.0 # (20+30+40)/3

def test_ma_nan_handling():
    ma = StreamingMA(window=3)
    ma.update(10.0)
    res = ma.update(float('nan'))
    assert res == 10.0
    # Nan should not affect the state
    res2 = ma.update(20.0)
    assert res2 == 15.0 # (10+20)/2

def test_autoscale_normal_data():
    data = np.array([10.0, 20.0, 30.0])
    ymin, ymax = compute_autoscale_range(data, padding_frac=0.1, min_range=0.0)
    # Range = 20. Pad = 2. ymin = 8, ymax = 32
    assert math.isclose(ymin, 8.0)
    assert math.isclose(ymax, 32.0)

def test_autoscale_flat_signal():
    data = np.array([10.0, 10.0, 10.0])
    ymin, ymax = compute_autoscale_range(data, padding_frac=0.1, min_range=1.0)
    # Mid = 10. min_range = 1. ymin = 9.5, ymax = 10.5
    # Then padding: range=1. pad=0.1. ymin=9.4, ymax=10.6
    assert math.isclose(ymin, 9.4)
    assert math.isclose(ymax, 10.6)

def test_autoscale_with_nan_inf():
    data = np.array([10.0, float('nan'), 20.0, float('inf')])
    ymin, ymax = compute_autoscale_range(data, padding_frac=0.0, min_range=0.0)
    assert math.isclose(ymin, 10.0)
    assert math.isclose(ymax, 20.0)

def test_autoscale_empty_array():
    data = np.array([])
    ymin, ymax = compute_autoscale_range(data)
    assert ymin == -1.0
    assert ymax == 1.0

def test_autoscale_ignore_zeros():
    data = np.array([0.0, 0.0, 0.0, 10.0, 20.0])
    ymin, ymax = compute_autoscale_range(data, padding_frac=0.0, ignore_zeros=True)
    assert math.isclose(ymin, 10.0)
    assert math.isclose(ymax, 20.0)
