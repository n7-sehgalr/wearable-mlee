"""Streaming signal filters for real-time EIT display.

Provides lightweight, O(1)-per-sample filter implementations suitable
for the GUI render loop.  These never touch the raw data written to disk;
they only produce smoothed values for the live plot.
"""
from __future__ import annotations

import math
import collections
from typing import Optional

import numpy as np


class StreamingEMA:
    """Exponential Moving Average with configurable cutoff frequency.

    Parameters
    ----------
    cutoff_hz : float
        Desired low-pass cutoff frequency (Hz).
    sample_rate_hz : float
        Approximate input sample rate (Hz).  Used to compute *alpha*.
        Can be updated at runtime via :meth:`set_sample_rate`.
    """

    def __init__(self, cutoff_hz: float = 0.8,
                 sample_rate_hz: float = 700.0):
        self._cutoff_hz = cutoff_hz
        self._sample_rate_hz = sample_rate_hz
        self._alpha: float = self._compute_alpha()
        self._value: Optional[float] = None

    # ------------------------------------------------------------------
    @staticmethod
    def _safe_alpha(cutoff_hz: float, sample_rate_hz: float) -> float:
        """Compute EMA alpha, clamped to [0, 1]."""
        if sample_rate_hz <= 0.0 or cutoff_hz <= 0.0:
            return 1.0  # pass-through
        raw = 1.0 - math.exp(-2.0 * math.pi * cutoff_hz / sample_rate_hz)
        return max(0.0, min(1.0, raw))

    def _compute_alpha(self) -> float:
        return self._safe_alpha(self._cutoff_hz, self._sample_rate_hz)

    # ------------------------------------------------------------------
    def set_sample_rate(self, sample_rate_hz: float) -> None:
        """Update the sample rate (and therefore alpha)."""
        self._sample_rate_hz = sample_rate_hz
        self._alpha = self._compute_alpha()

    def set_cutoff(self, cutoff_hz: float) -> None:
        """Update the cutoff frequency."""
        self._cutoff_hz = cutoff_hz
        self._alpha = self._compute_alpha()

    @property
    def alpha(self) -> float:
        return self._alpha

    @property
    def value(self) -> Optional[float]:
        return self._value

    # ------------------------------------------------------------------
    def update(self, sample: float) -> float:
        """Feed one sample, return the filtered value.

        On the very first call the filter output equals the input (no
        ringing / step response).
        """
        if not math.isfinite(sample):
            # Ignore NaN / Inf — return last good value or 0.0
            return self._value if self._value is not None else 0.0

        if self._value is None:
            self._value = sample
        else:
            self._value = self._alpha * sample + (1.0 - self._alpha) * self._value
        return self._value

    def reset(self) -> None:
        """Clear filter state so the next sample re-initialises it."""
        self._value = None


class StreamingMA:
    """Streaming Moving Average using a bounded deque.

    Amortised O(1) per sample.  The window is filled gradually during
    start-up — the average is computed over however many samples are
    available so far.

    Parameters
    ----------
    window : int
        Number of samples in the moving-average window.
    """

    def __init__(self, window: int = 400):
        if window < 1:
            window = 1
        self._window = window
        self._buf: collections.deque[float] = collections.deque(maxlen=window)
        self._sum: float = 0.0

    @property
    def value(self) -> Optional[float]:
        if not self._buf:
            return None
        return self._sum / len(self._buf)

    def update(self, sample: float) -> float:
        """Feed one sample, return the moving average."""
        if not math.isfinite(sample):
            v = self.value
            return v if v is not None else 0.0

        # If the deque is full, subtract the oldest value that will be evicted
        if len(self._buf) == self._window:
            self._sum -= self._buf[0]

        self._buf.append(sample)
        self._sum += sample
        return self._sum / len(self._buf)

    def reset(self) -> None:
        """Clear the buffer."""
        self._buf.clear()
        self._sum = 0.0


def compute_autoscale_range(
    data: np.ndarray,
    padding_frac: float = 0.10,
    min_range: float = 0.005,
    ignore_zeros: bool = True,
) -> tuple[float, float]:
    """Compute a stable Y-axis range for *data*.

    Parameters
    ----------
    data : np.ndarray
        1-D array of display values.
    padding_frac : float
        Fraction of the data range added as padding above and below.
    min_range : float
        Minimum allowed range (prevents jitter on flat signals).
    ignore_zeros : bool
        If *True*, leading zeros (uninitialised ring-buffer slots) are
        excluded from the range calculation.

    Returns
    -------
    (y_min, y_max) : tuple[float, float]
    """
    if data.size == 0:
        return (-1.0, 1.0)

    # Mask out non-finite values
    valid = data[np.isfinite(data)]

    if ignore_zeros:
        # Find first non-zero to skip uninitialised buffer
        nonzero = np.nonzero(valid)[0]
        if nonzero.size > 0:
            valid = valid[nonzero[0]:]

    if valid.size == 0:
        return (-1.0, 1.0)

    y_min = float(np.min(valid))
    y_max = float(np.max(valid))

    data_range = y_max - y_min
    if data_range < min_range:
        mid = (y_min + y_max) / 2.0
        y_min = mid - min_range / 2.0
        y_max = mid + min_range / 2.0
        data_range = min_range

    pad = data_range * padding_frac
    return (y_min - pad, y_max + pad)
