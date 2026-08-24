"""
 Authors: Nils Gumpfer, Joshua Prim
 Version: 0.1

 Utils for extraction

 Copyright 2020 The Authors. All Rights Reserved.
"""
import pandas as pd
import numpy as np
from scipy.interpolate import Akima1DInterpolator
from scipy.signal import savgol_filter
import math
import logging
import matplotlib.pyplot as plt
def rotate_origin_only(x, y, radians):
    """
        rotates one point around the origin
    :param x: point X-axis
    :param y: point Y-axis
    :param radians:
    :return: rotated point
    """
    xx = x * math.cos(radians) + y * math.sin(radians)
    yy = -x * math.sin(radians) + y * math.cos(radians)

    return xx, yy


def move_along_the_axis(lead_list, index=0):
    """
        move along the axis
    :param lead_list:
    :param index: point for orientation of the origin
    :return: new lead list
    """
    tmp = 0
    for (x, y), i in zip(lead_list, range(len(lead_list))):
        if x < index:
            tmp = i

    x0, y0 = lead_list[tmp]
    tmp = [(x, y - y0) for x, y in lead_list]

    delta = index - tmp[0][0]

    new_lead_list = []
    for i in tmp:
        new_lead_list.append((i[0] + delta, i[1]))

    return new_lead_list


def get_y_value(x, list_x, list_y):
    """
        returns the Y value of a transferred X value based on the transferred list of values.
    :param x: x Value
    :param list_x: list of X-values
    :param list_y: list of Y-values
    :return: y value
    """
    x_value, index = find_value1_value2(list_x, x)
    y_value = [list_y[index - 1], list_y[index]]

    denom = x_value[0] - x_value[1]
    if abs(denom) < 1e-12:
        return (y_value[0] + y_value[1]) / 2
    m = (y_value[0] - y_value[1]) / denom
    b = (x_value[0] * y_value[1] - x_value[1] * y_value[0]) / denom
    y = m * x + b
    return y


def find_value1_value2(liste, value):
    """
        finds the next smaller and larger value in a list for a passed value.
    :param liste: list to be searched
    :param value: value
    :return: lower value, upper value and index
    """
    tmp_array = np.array(liste)
    index = np.where(tmp_array > value)[0][0]

    value1 = 0 if index == 0 else liste[index - 1]
    value2 = liste[index]

    return [value1, value2], index


def scale_values_based_on_eich_peak(lead_list, gamma=0.5):
    """
        scale values on the Y-axis
        :param lead_list: list of the value
        :param gamma: scaling factor
        :return: rescaled list
    """
    new_lead_list = []
    for xy_pair in lead_list:
        new_y_value = xy_pair[1] * gamma
        new_lead_list.append([xy_pair[0], new_y_value])
    return new_lead_list


def plot_leads(lead, plot_path=None, plot_name='plot'):
    """
        visualizes the lead in a plot
    :param lead: ecg lead for visualization
    :param plot_path: path where the plot should be saved if set
    :param plot_name: name of the plot to be saved
    """
    df = pd.DataFrame(lead, columns=['Y', 'extracted time series'])
    df['extracted time series'] = pd.to_numeric(df['extracted time series'])
    df['Y'] = pd.to_numeric(df['Y'])

    df.plot(kind='line', x='Y', y=['extracted time series'], figsize=(20, 10), legend=False)
    # df.plot(kind='line', x='Y', y=['extracted time series'], figsize=(28, 2), legend=False)

    if plot_path is not None:
        plt.savefig(plot_path + str(plot_name) + '.png')

    plt.show()


def create_measurement_points(lead_list, number_of_points, target_x=None):
    """
        creates measuring points at equidistant intervals from each other using Akima spline interpolation.
        Akima splines are shape-preserving (no overshoot on sharp features like QRS complexes) and
        eliminate flat-line artifacts that occur with linear interpolation between sparse source points.
        Pre-smoothing of raw PDF Y values removes quantization noise before interpolation to prevent
        baseline jitter that would otherwise be amplified by the spline.
        A shared target_x grid (common time window across all leads of one ECG) keeps all leads
        temporally aligned; without it, each lead is mapped onto its own ink extent, which
        introduces per-lead time offsets.
    :param lead_list: list with lead [[x, y], ...]
    :param number_of_points: number of measuring points to be created
    :param target_x: optional shared X grid (np.ndarray) spanning the common time window
    :return: numpy array of interpolated Y values (float64)
    """
    x_values = np.array([p[0] for p in lead_list])
    y_values = np.array([p[1] for p in lead_list])

    # Sort by X to ensure monotonicity (required by Akima spline)
    sort_idx = np.argsort(x_values)
    x_sorted, y_sorted = x_values[sort_idx], y_values[sort_idx]

    # Deduplicate: average Y values at identical X coordinates (Akima requires strictly increasing X)
    if len(x_sorted) > 1:
        unique_x, indices = np.unique(x_sorted, return_index=True)
        if len(unique_x) < len(x_sorted):
            x_unique = []
            y_unique = []
            for ux in unique_x:
                mask = x_sorted == ux
                x_unique.append(ux)
                y_unique.append(float(np.mean(y_sorted[mask])))
            x_sorted, y_sorted = np.array(x_unique), np.array(y_unique)

    # NOTE: smoothing is applied AFTER interpolation on the uniform target grid.
    # Pre-smoothing the sparse source points with a Savitzky-Golay filter assumes
    # equally spaced samples, but PDF ink point density varies within and between
    # leads (pen speed), which systematically shifted QRS features in time by up to
    # ~20 samples (~40 ms). On the uniform grid the symmetric filter introduces no
    # time delay while still removing quantization jitter.
    if target_x is None:
        min_x, max_x = x_sorted[0], x_sorted[-1]
        target_x = np.linspace(min_x, max_x, number_of_points)

    if len(x_sorted) >= 4:
        interp = Akima1DInterpolator(x_sorted, y_sorted)
        result = interp(target_x)
    else:
        # Fallback to linear interpolation for very short segments (< 4 points)
        from scipy.interpolate import interp1d
        interp_fn = interp1d(x_sorted, y_sorted, kind='linear', fill_value='extrapolate')
        result = interp_fn(target_x)

    if len(result) >= 11:
        result = savgol_filter(result, window_length=11, polyorder=2)
    elif len(result) >= 5:
        result = savgol_filter(result, window_length=5, polyorder=2)

    return result


def common_time_window(lead_arrays):
    """
        Returns the common (intersection) time window [t_lo, t_hi] across all leads,
        i.e. the interval covered by EVERY lead's ink. Falls back to the global
        union window if the intersection is empty or degenerate.
    :param lead_arrays: list of np.ndarray segments with time in column 0
    :return: (t_lo, t_hi) floats
    """
    t_lo = max(float(np.min(a[:, 0])) for a in lead_arrays)
    t_hi = min(float(np.max(a[:, 0])) for a in lead_arrays)
    if t_hi <= t_lo:
        logging.warning('Lead time windows do not overlap; falling back to union window.')
        t_lo = min(float(np.min(a[:, 0])) for a in lead_arrays)
        t_hi = max(float(np.max(a[:, 0])) for a in lead_arrays)
    return t_lo, t_hi


def calc_stddev(df, window_size=124):
    """
        calculates the average using the standard deviation
        Note: the procedure is only executed on the first lead
    :param df: DataFrame which is scanned
    :param window_size: size of the sliding window
    :return: average
    """
    min_dev_sum = np.inf
    avg = []
    for i in range(0, len(df) - window_size):
        df_tmp = df.loc[i:i + window_size]

        if sum(df_tmp.std()) < min_dev_sum:
            min_dev_sum = sum(df_tmp.std())
            avg = df_tmp.mean()
    return avg


def preprocess_page_content(page_content_bytes):
    """
        Preprocesses the content bytes from the PDFs (already decompressed by PyPDF2).
    :param page_content_bytes: decoded content bytes from page.get_contents()[0].get_data()
    :return: latin-1 decoded content string
    """
    return page_content_bytes.decode('latin-1')


def extract_graphics_string(page_content):
    """
        Process the content string until it only holds only necessary graphical information for content extraction
    :param page_content: The content of the page
    :return: Graphical string
    """
    graphics_string = page_content.replace(' l', '').replace(' m', '').replace(' w', '').replace(' j', '').replace(' J',
                                                                                                                    '')
    graphics_string = graphics_string.split('Q')

    return graphics_string


def parse_schiller_waveforms(page_content_bytes):
    """Parse Schiller PDF page into waveform segments.

    Schiller PDFs use raw m/l operators without Q/C block delimiters.
    Each page has 6 waveforms (~715 pts each, X_span≈708), plus grid lines
    at page margins and an Eichzacke calibration mark.

    Returns list of np.ndarray segments (shape: [N, 2]), sorted by Y center.
    """
    import re

    raw = page_content_bytes.decode('latin-1')
    cleaned = re.sub(r'\([^)]*\)', '', raw)
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    cleaned = re.sub(r'BT.*?ET', '', cleaned, flags=re.DOTALL)

    # Parse operators separately: 'm' starts a segment, 'l' continues it
    ops = re.findall(r'(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+([ml])', cleaned)
    if not ops:
        return []

    segments = []
    current_seg = None
    for px_s, py_s, op in ops:
        px, py = float(px_s), float(py_s)
        if op == 'm':
            if current_seg is not None:
                segments.append(current_seg)
            current_seg = [(px, py)]
        elif op == 'l' and current_seg is not None:
            current_seg.append((px, py))
    if current_seg is not None:
        segments.append(current_seg)

    # Filter: keep only waveform-like segments (50-2000 pts, X_span > 300)
    waveforms = []
    for seg in segments:
        if len(seg) < 50 or len(seg) > 2000:
            continue
        xs = [p[0] for p in seg]
        ys = [p[1] for p in seg]
        x_span = max(xs) - min(xs)
        y_span = max(ys) - min(ys)
        if x_span < 300:
            continue
        if y_span < 5 and len(seg) > 100:
            continue
        waveforms.append(np.array(seg))

    # Sort by Y center descending: PDF Y=0 is at bottom, so highest Y = top of page = lead I/V1
    waveforms.sort(key=lambda w: np.mean(w[:, 1]), reverse=True)
    return waveforms[:6]  # exactly 6 per page


def extract_eichzacke_from_page_bytes(page_content_bytes, manufacturer='cardiosoft'):
    """
        Dynamically extract the Eichzacke (calibration square) dimensions from raw PDF page bytes.

        For Cardiosoft: The calibration square is drawn in S-blocks 18-24 of the full content stream.
            Blocks 18-20 = top horizontal edge, block 21 = vertical edge, block 22 = bottom edge,
            blocks 23-24 = tick marks above/below.

        For Schiller: The Eichzacke is a small 6-point stepped/arrow shape at X=[38-52], Y_span≈28.35 units.

    :param page_content_bytes: raw bytes from page.get_contents().get_data()
    :param manufacturer: 'cardiosoft' or 'schiller'
    :return: float — the Eichzacke span in the amplitude direction. For Cardiosoft this is the X span
             (maps to amplitude after 90° rotation). Returns None if extraction fails.
    """
    import re

    raw = page_content_bytes.decode('latin-1')

    # Strip text content but preserve drawing operators
    cleaned = re.sub(r'\([^)]*\)', '', raw)
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    cleaned = re.sub(r'BT.*?ET', '', cleaned, flags=re.DOTALL)

    if manufacturer == 'cardiosoft':
        # Split by stroke operator 'S'
        s_blocks = re.split(r'\bS\b', cleaned)
        eich_start, eich_end = 18, 23

        all_eich_x, all_eich_y = [], []
        for bi in range(eich_start, min(eich_end, len(s_blocks))):
            block = s_blocks[bi]
            # Extract coordinate pairs from "number number m" or "number number l" commands
            ml_matches = re.findall(r'(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+[ml]', block)
            for mx, my in ml_matches:
                all_eich_x.append(float(mx))
                all_eich_y.append(float(my))

        if len(all_eich_x) < 2:
            return None

        x_span = max(all_eich_x) - min(all_eich_x)
        y_span = max(all_eich_y) - min(all_eich_y)

        # The Eichzacke Y span is the amplitude-direction reference (before rotation).
        if y_span > 10:
            return y_span
        elif x_span > 10:
            return x_span
        else:
            return None

    elif manufacturer == 'schiller':
        # Schiller Eichzacke is a small stepped/arrow shape at X=[38-52], Y_span≈28.35 (page 0), ≈23.70 (page 1).
        # Parse operators separately: 'm' starts a segment, 'l' continues it.

        ops = re.findall(r'(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+([ml])', cleaned)
        if not ops:
            return None

        segments = []
        current_seg = None
        for px_s, py_s, op in ops:
            px, py = float(px_s), float(py_s)
            if op == 'm':
                if current_seg is not None:
                    segments.append(current_seg)
                current_seg = [(px, py)]
            elif op == 'l' and current_seg is not None:
                current_seg.append((px, py))
        if current_seg is not None:
            segments.append(current_seg)

        # Find Eichzacke: small segment (3-15 pts), X in [20, 80], Y_span in [15, 50]
        for seg in segments:
            if not (3 <= len(seg) <= 15):
                continue
            xs = [p[0] for p in seg]
            ys = [p[1] for p in seg]
            x_min, x_max = min(xs), max(xs)
            y_span = max(ys) - min(ys)
            if 20 <= x_min and x_max <= 80 and 15 <= y_span <= 50:
                return y_span

        # Fallback: scan all points for the Eichzacke X region
        eich_y = []
        for px_s, py_s, op in ops:
            px, py = float(px_s), float(py_s)
            if 20 <= px <= 80:
                eich_y.append(py)
        if len(eich_y) >= 2:
            y_span = max(eich_y) - min(eich_y)
            if y_span > 15:
                return y_span

        return None

    return None


def clip_preamble_points(leads, orientation='vertical'):
    """Remove preamble points from Cardiosoft segments that extend below the waveform start.

    In Cardiosoft PDFs, the last segment per page (segment 13) sometimes includes
    grid/calibration points at Y < waveform_start (vertical) or X < waveform_start
    (horizontal), inflating the time-axis span and causing temporal misalignment.
    This function clips only the last segment using a median-based threshold on the
    time-axis dimension, leaving earlier segments untouched.

    :param leads: list of np.ndarray segments (shape: [N, 2])
    :param orientation: 'vertical' (clip by Y) or 'horizontal' (clip by X)
    :return: list of clipped np.ndarray segments
    """
    if not leads:
        return leads

    axis = 1 if orientation == 'vertical' else 0
    mins = [np.min(arr[:, axis]) for arr in leads]
    median_min = float(np.median(mins))

    clipped = []
    for i, arr in enumerate(leads):
        if i == len(leads) - 1:
            mask = arr[:, axis] >= median_min
            clipped.append(arr[mask])
        else:
            clipped.append(arr)
    return clipped


def adjust_leads_baseline(df_leads):
    stddev_tmp = calc_stddev(df_leads)

    for column in df_leads.columns:
        df_leads[column] = df_leads[column] - stddev_tmp[column]

    return df_leads
