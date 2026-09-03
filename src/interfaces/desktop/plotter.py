import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt

from src.interfaces.desktop.constants import (
    EIT_SMOOTHING_METHOD, EIT_EMA_CUTOFF_HZ, EIT_MA_WINDOW_SAMPLES,
    EIT_DISPLAY_MAX_POINTS, EIT_AUTOSCALE_PADDING, EIT_AUTOSCALE_MIN_RANGE,
    EIT_AUTOSCALE_HYSTERESIS, EIT_RAW_CURVE_ALPHA,
    MARKER_COLORS, MARKER_MAX_VISIBLE_ANNOTATIONS,
)
from src.interfaces.desktop.filters import StreamingEMA, StreamingMA, compute_autoscale_range

class DataPlotter(pg.PlotWidget):
    """Real-time scrolling plot with optional smoothing and marker annotations.
    
    Two modes:
    1. Standard (IMU plots): simple ring buffer, Y autoscale or fixed range
    2. EIT mode (enable_smoothing=True): dual raw+smoothed curves, streaming filter,
       smart autoscale, marker annotations
    """
    
    def __init__(self, title, labels=None, colors=None, max_points=500,
                 enable_smoothing=False, smoothing_method='ema',
                 ema_cutoff_hz=0.8, ma_window=400):
        super().__init__()
        
        self.setTitle(title, color='w', size='10pt')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.addLegend(offset=(10, 10))
        self.setLabel('bottom', 'Time', units='s')
        
        self.max_points = max_points
        self.enable_smoothing = enable_smoothing
        self.labels = labels or ["Data"]
        colors = colors or [(255, 0, 0)]
        
        self.data_buffers = {label: np.zeros(max_points) for label in self.labels}
        self.time_buffer = np.zeros(max_points)
        
        self.curves = []
        self.raw_curves = []
        
        self.filters = {}
        self.smoothed_buffers = {}
        
        if self.enable_smoothing:
            for label in self.labels:
                self.smoothed_buffers[label] = np.zeros(max_points)
                if smoothing_method == 'ema':
                    self.filters[label] = StreamingEMA(cutoff_hz=ema_cutoff_hz)
                else:
                    self.filters[label] = StreamingMA(window=ma_window)
                    
        for i, label in enumerate(self.labels):
            color = colors[i % len(colors)]
            if self.enable_smoothing:
                # Semi-transparent raw curve
                raw_pen = pg.mkPen(color=color + (EIT_RAW_CURVE_ALPHA,), width=1)
                smooth_pen = pg.mkPen(color=color, width=2)
                
                raw_curve = self.plot(pen=raw_pen, name=f"{label} (Raw)")
                smooth_curve = self.plot(pen=smooth_pen, name=f"{label} (Filtered)")
                
                self.raw_curves.append((label, raw_curve))
                self.curves.append((label, smooth_curve))
            else:
                pen = pg.mkPen(color=color, width=2)
                curve = self.plot(pen=pen, name=label)
                self.curves.append((label, curve))
                
        self.ptr = 0
        self._dirty = False
        self._last_y_range = None
        self._marker_lines = []
        
        self.enableAutoRange(axis='x', enable=False)
        self.enableAutoRange(axis='y', enable=False)
        
    def append_sample(self, t: float, values: list[float]):
        self.append_samples([t], [values])
        
    def append_samples(self, times: list[float], values_list: list[list[float]]):
        """Append multiple samples efficiently."""
        n = len(times)
        if n == 0:
            return
            
        # If we are adding more points than the buffer holds, just take the last max_points
        if n >= self.max_points:
            times = times[-self.max_points:]
            values_list = values_list[-self.max_points:]
            n = self.max_points

        # Shift arrays by n
        self.time_buffer[:-n] = self.time_buffer[n:]
        self.time_buffer[-n:] = times
        
        for i, label in enumerate(self.labels):
            vals = [v[i] for v in values_list]
            self.data_buffers[label][:-n] = self.data_buffers[label][n:]
            self.data_buffers[label][-n:] = vals
            
            if self.enable_smoothing:
                # Update filter for each value
                filtered = [self.filters[label].update(v) for v in vals]
                self.smoothed_buffers[label][:-n] = self.smoothed_buffers[label][n:]
                self.smoothed_buffers[label][-n:] = filtered
                
        self.ptr = min(self.max_points, self.ptr + n)
        self._dirty = True
        
    def redraw(self):
        """Redraw curves from ring buffer. Called from GUI timer."""
        if not self._dirty:
            return
        self._dirty = False
        
        start = max(0, self.max_points - self.ptr)
        t_data = self.time_buffer[start:]
        
        if len(t_data) == 0:
            return
            
        self.setXRange(t_data[0], t_data[-1], padding=0)
        
        all_y = []
        for label, curve in self.curves:
            if self.enable_smoothing:
                y = self.smoothed_buffers[label][start:]
            else:
                y = self.data_buffers[label][start:]
            curve.setData(t_data, y)
            all_y.extend(y)
            
        for label, curve in self.raw_curves:
            y_raw = self.data_buffers[label][start:]
            curve.setData(t_data, y_raw)
            all_y.extend(y_raw)
            
        # Autoscale with hysteresis
        if all_y:
            y_min, y_max = compute_autoscale_range(
                np.array(all_y),
                padding_frac=EIT_AUTOSCALE_PADDING,
                min_range=EIT_AUTOSCALE_MIN_RANGE
            )
            
            if self._last_y_range is None:
                self._last_y_range = (y_min, y_max)
                self.setYRange(y_min, y_max, padding=0)
            else:
                old_min, old_max = self._last_y_range
                old_range = old_max - old_min
                if (abs(y_min - old_min) > EIT_AUTOSCALE_HYSTERESIS * old_range or
                    abs(y_max - old_max) > EIT_AUTOSCALE_HYSTERESIS * old_range):
                    self.setYRange(y_min, y_max, padding=0)
                    self._last_y_range = (y_min, y_max)
                    
        self.cleanup_markers()
        
    def add_marker(self, t: float, key: str, event: str, color: str):
        """Add a vertical marker line at time t with label."""
        line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(color, width=2, style=Qt.PenStyle.DashLine))
        line.setPos(t)
        
        label = pg.TextItem(text=f"[{key.upper()}] {event}", color=color, anchor=(0, 1))
        label.setParentItem(line)
        label.setPos(0, 0)
        
        self.addItem(line)
        self._marker_lines.append({'t': t, 'line': line})
        
    def cleanup_markers(self):
        """Remove marker annotations that are outside the visible X range."""
        if self.ptr == 0:
            return
        t_min = self.time_buffer[self.max_points - self.ptr]
        
        to_remove = []
        for marker in self._marker_lines:
            if marker['t'] < t_min:
                to_remove.append(marker)
                
        # Enforce max limit
        if len(self._marker_lines) - len(to_remove) > MARKER_MAX_VISIBLE_ANNOTATIONS:
            excess = (len(self._marker_lines) - len(to_remove)) - MARKER_MAX_VISIBLE_ANNOTATIONS
            for marker in self._marker_lines:
                if marker not in to_remove and excess > 0:
                    to_remove.append(marker)
                    excess -= 1
                    
        for marker in to_remove:
            self.removeItem(marker['line'])
            self._marker_lines.remove(marker)
            
    def reset(self):
        """Clear all data and markers. Called when starting a new session."""
        self.time_buffer.fill(0)
        for label in self.labels:
            self.data_buffers[label].fill(0)
            if self.enable_smoothing:
                self.smoothed_buffers[label].fill(0)
                self.filters[label].reset()
        self.ptr = 0
        self._dirty = False
        self._last_y_range = None
        
        for marker in self._marker_lines:
            self.removeItem(marker['line'])
        self._marker_lines.clear()
