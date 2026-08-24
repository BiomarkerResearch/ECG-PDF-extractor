"""
Extract clinical metadata directly from ECG PDF text (Cardiosoft and Schiller).

Parses patient name, ID, date/time, sex, age, speed, duration, leads, heart rate,
and measured intervals from the first page of each ECG PDF.
"""
import re


def detect_manufacturer(pdf_bytes):
    """Auto-detect ECG manufacturer from PDF text content.

    Returns 'Cardiosoft', 'Schiller', or None if undetermined.
    """
    import PyPDF2
    import io

    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    text = reader.pages[0].extract_text()

    cardio_score = 0
    schiller_score = 0

    # Cardiosoft indicators
    if 'GE CardioSoft' in text:
        cardio_score += 3
    if 'Herzfrequenz' in text:
        cardio_score += 2
    if 'Patienten-Nr.' in text:
        cardio_score += 1
    if 'P-QRS-T Winkel' in text:
        cardio_score += 1
    if 'QRS Dauer' in text:
        cardio_score += 1

    # Schiller indicators
    if re.search(r'AT[-\u2011]\d+[A-Z]?', text):
        schiller_score += 3
    if 'SINUSRHYTHMUS' in text or 'LAGETYP NORMAL' in text:
        schiller_score += 2
    if 'QRS-Achse' in text or 'P-Achse' in text:
        schiller_score += 1
    if re.search(r'Pat[\.\u2011\s]*-?\s*ID', text):
        schiller_score += 1

    if cardio_score > schiller_score and cardio_score >= 2:
        return 'Cardiosoft'
    elif schiller_score > cardio_score and schiller_score >= 2:
        return 'Schiller'
    return None


def extract_cardiosoft_metadata(text):
    """Extract metadata from Cardiosoft (GE CardioSoft) PDF text."""
    meta = {}

    # --- Name: "LastName, FirstName" — may share a line with Patienten-Nr ---
    lines = text.split('\n')
    for line in lines[:5]:
        if any(kw in line for kw in ['Seite', 'RUHE-EKG']):
            continue
        m_name = re.search(r'^(.+?),\s*\w+\s+(?:Patienten-Nr\.:.*)?$', line)
        if m_name:
            meta['name'] = m_name.group(0).split('Patienten-Nr')[0].strip()
            break
        if re.search(r',\s*\w+', line):
            meta['name'] = line.strip().split('Patienten-Nr')[0].strip()
            break

    # --- Patient number: "Patienten-Nr.: 1247165" ---
    m = re.search(r'Patienten-Nr\.:\s*(\d+)', text)
    if m:
        meta['patient_id'] = m.group(1)

    # --- Date and time: "29.04.2025" + " 8:28:13männlich" ---
    m_date = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
    if m_date:
        meta['ecg_date'] = m_date.group(1)

    m_time = re.search(r'\b(\d{1,2}:\d{2}:\d{2})', text)
    if m_time:
        meta['ecg_time'] = m_time.group(1)

    # --- Sex: "männlich" or "weiblich" ---
    if 'männlich' in text.lower():
        meta['sex'] = 'male'
    elif 'weiblich' in text.lower():
        meta['sex'] = 'female'

    # --- Age: "75J." ---
    m_age = re.search(r'(\d{1,3})\s*J\.?', text)
    if m_age:
        meta['age'] = int(m_age.group(1))

    # --- Speed: "50mm/s" or "25 mm/s" ---
    m_speed = re.search(r'(\d+)\s*mm/s', text)
    if m_speed:
        meta['speed_mm_s'] = int(m_speed.group(1))

    # --- Duration format: "3 * 5s", "10s", etc. ---
    m_dur = re.search(r'(?:3\s*\*\s*5s|10s)', text)
    if m_dur:
        meta['duration'] = m_dur.group(0).replace(' ', '')

    # --- Available leads from page text (last 6 non-artifact lines) ---
    clean_lines = [l for l in lines if len(l) <= 50 or len(set(l.strip())) > 1]
    lead_ids = []
    for lid in clean_lines[-6:]:
        lid = re.sub(r'^(.)\1{4,}', '', lid).strip()
        if lid in ('I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6'):
            lead_ids.append(lid)
    meta['available_leads'] = ','.join(lead_ids) if lead_ids else ''

    # --- Heart rate: "Herzfrequenz 55/min" ---
    m_hr = re.search(r'Herzfrequenz\s+(\d+)\s*/min', text)
    if m_hr:
        meta['heart_rate'] = int(m_hr.group(1))

    # --- Intervals: PQ, QRS, QT/QTc ---
    m_pq = re.search(r'PQ\s+Intervall\s+(\d+)\s*ms', text)
    if m_pq:
        meta['pq_ms'] = int(m_pq.group(1))

    m_qrs = re.search(r'QRS\s*Dauer\s+(\d+)\s*ms', text)
    if m_qrs:
        meta['qrs_ms'] = int(m_qrs.group(1))

    m_qt = re.search(r'QT/QTc\s+(\d+)/(\d+)ms', text)
    if m_qt:
        meta['qt_ms'] = int(m_qt.group(1))
        meta['qtc_ms'] = int(m_qt.group(2))

    # --- Axes: "P-QRS-T Winkel 66/86/23°" ---
    m_axes = re.search(r'P-QRS-T\s+Winkel\s+(\d+)/(\d+)/(\d+)°', text)
    if m_axes:
        meta['p_axis'] = int(m_axes.group(1))
        meta['qrs_axis'] = int(m_axes.group(2))
        meta['t_axis'] = int(m_axes.group(3))

    # --- P duration ---
    m_pdur = re.search(r'P\s*Dauer\s+(\d+)\s*ms', text)
    if m_pdur:
        meta['p_duration_ms'] = int(m_pdur.group(1))

    # --- RR/PP interval ---
    m_rrpp = re.search(r'RR/PP\s+Intervall\s+(\d+)/(\d+)ms', text)
    if m_rrpp:
        meta['rr_interval_ms'] = int(m_rrpp.group(1))
        meta['pp_interval_ms'] = int(m_rrpp.group(2))

    # --- Software version ---
    m_ver = re.search(r'GE\s+CardioSoft\s+V?([\d.]+)', text)
    if m_ver:
        meta['software_version'] = m_ver.group(1)

    return meta


def extract_schiller_metadata(text):
    """Extract metadata from Schiller PDF text."""
    meta = {}

    lines = text.split('\n')

    # --- Name and Patient ID from header block ---
    # "Pat.‑IDtest testmann" — may use non-breaking hyphen (U+2011), no space after ID
    for line in lines[:10]:
        if 'Pat' in line and 'ID' in line:
            m = re.search(r'Pat[\.\u2011\s]*-?\s*ID\s*(.+)', line)
            if m:
                meta['name'] = m.group(1).strip()
            break

    # --- Patient number: digits near date ---
    # "128242305.02.2021 13:39:33" -> patient_id=1282423, date=05.02.2021
    m_patdate = re.search(r'(\d{6,8})(\d{2}\.\d{2}\.\d{4})', text)
    if m_patdate:
        meta['patient_id'] = m_patdate.group(1)
        meta['ecg_date'] = m_patdate.group(2)

    # --- Time ---
    m_time = re.search(r'\b(\d{2}:\d{2}:\d{2})\b', text)
    if m_time:
        meta['ecg_time'] = m_time.group(1)

    # --- Sex: "Männlich" or "Weiblich" ---
    if re.search(r'Männlich|male', text, re.IGNORECASE):
        meta['sex'] = 'male'
    elif re.search(r'Weiblich|female', text, re.IGNORECASE):
        meta['sex'] = 'female'

    # --- Age: "020Y" or "20J." ---
    m_age = re.search(r'(?:Alter\s+)?(\d{1,3})\s*[YJ]', text)
    if m_age:
        meta['age'] = int(m_age.group(1))

    # --- Birth date: "Geb.-datum" label, value up to 15 lines later (two-column layout) ---
    for i, line in enumerate(lines):
        if 'Geb.' in line and 'datum' in line.lower():
            for j in range(i + 1, min(i + 16, len(lines))):
                m_bd = re.search(r'(\d{2}\.\d{2}\.\d{4})', lines[j])
                if m_bd:
                    meta['birth_date'] = m_bd.group(1)
                    break
            break

    # --- Ethnicity: "Weiss" etc. ---
    for line in lines[:30]:
        if 'Weiss' in line or 'Schwarz' in line or 'Asiatisch' in line:
            meta['ethnicity'] = re.search(r'(Weiss|Schwarz|Asiatisch)', line).group(1)
            break

    # --- Speed: "25 mm/s" or "50mm/s" ---
    m_speed = re.search(r'(\d+)\s*mm/s', text)
    if m_speed:
        meta['speed_mm_s'] = int(m_speed.group(1))

    # --- Duration format: "Rhythmen 10s", etc. ---
    m_dur = re.search(r'(?:Rhythmen\s+)?(\d+)s', text)
    if m_dur:
        meta['duration'] = f"{m_dur.group(1)}s"

    # --- Available leads from page text ---
    all_leads = []
    for lid in lines:
        lid = lid.strip()
        if lid in ('I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6'):
            all_leads.append(lid)
    meta['available_leads'] = ','.join(all_leads) if all_leads else ''

    # --- Heart rate: "HF" label, value with "/min" may be several lines later ---
    hf_pos = text.find('HF')
    m_hr = None
    if hf_pos >= 0:
        window = text[hf_pos:hf_pos + 120]
        m_hr = re.search(r'(\d{2,3})\s*/min', window)
    if not m_hr:
        m_hr = re.search(r'HF\s+(\d+)\s*/?/min', text)
    if not m_hr:
        m_hr = re.search(r'(\d{2,3})\s*/min', text)
    if m_hr:
        meta['heart_rate'] = int(m_hr.group(1))

    # --- Axes from "P-Achse / QRS-Achse / T-Achse" section ---
    # Labels and values may be on separate line blocks (two-column layout).
    # Use positional pairing: find label lines, then value lines with ° after them.
    _axis_labels = ['P', 'QRS', 'T']
    _axis_label_positions = []
    for lbl in _axis_labels:
        pat = r'^\s*' + re.escape(lbl) + r'[\-\u2011\u2013]Achse\s*$'
        for li, ln in enumerate(lines):
            if re.match(pat, ln):
                _axis_label_positions.append((lbl, li))
                break
    if _axis_label_positions:
        last_axis_line = max(li for _, li in _axis_label_positions)
        _axis_values = []
        for vi in range(last_axis_line + 1, min(last_axis_line + 20, len(lines))):
            vm = re.match(r'^\s*(\d+)\s*°\s*$', lines[vi])
            if vm:
                _axis_values.append(int(vm.group(1)))
        # Don't break on first non-match — heart rate value may sit between labels and axis values
        for idx, (lbl, _) in enumerate(_axis_label_positions):
            if idx < len(_axis_values):
                val = _axis_values[idx]
                if lbl == 'P':
                    meta['p_axis'] = val
                elif lbl == 'QRS':
                    meta['qrs_axis'] = val
                elif lbl == 'T':
                    meta['t_axis'] = val

    # --- Intervals from "RR / P / PQ / QRS / QT / QTcB" section ---
    # Labels and values may be on separate line blocks (two-column layout).
    # Use positional pairing: find label lines, then value lines after them.
    _interval_labels = ['RR', 'P', 'PQ', 'QRS', 'QT', 'QTcB']
    _label_positions = []
    for lbl in _interval_labels:
        for li, ln in enumerate(lines):
            if re.match(r'^\s*' + re.escape(lbl) + r'\s*$', ln):
                _label_positions.append((lbl, li))
                break
    if _label_positions:
        last_label_line = max(li for _, li in _label_positions)
        _value_lines = []
        for vi in range(last_label_line + 1, min(last_label_line + 20, len(lines))):
            vm = re.match(r'^\s*(\d+)\s*ms\s*$', lines[vi])
            if vm:
                _value_lines.append(int(vm.group(1)))
            else:
                break
        for idx, (lbl, _) in enumerate(_label_positions):
            if idx < len(_value_lines):
                val = _value_lines[idx]
                if lbl == 'RR':
                    meta['rr_interval_ms'] = val
                elif lbl == 'P':
                    meta['p_duration_ms'] = val
                elif lbl == 'PQ':
                    meta['pq_ms'] = val
                elif lbl == 'QRS':
                    meta['qrs_ms'] = val
                elif lbl == 'QT':
                    meta['qt_ms'] = val
                elif lbl == 'QTcB':
                    meta['qtc_ms'] = val

    # --- Auto-interpretation text ---
    for kw in ['SINUSRHYTHMUS', 'LAGETYP NORMAL', 'SONST NORMALES EKG']:
        if kw in text:
            field = kw.lower().replace(' ', '_')
            meta[field] = True

    # --- Device info from footer ---
    # Handle both ASCII hyphen and non-breaking hyphen (U+2011), single/double colons
    m_dev = re.search(r'(AT[-\u2011]\d+[A-Z]?)::?\s*(SCM\s*\d+)', text)
    if m_dev:
        meta['device_model'] = m_dev.group(1).strip()
        meta['device_serial'] = m_dev.group(2).strip()

    return meta


def extract_metadata(pdf_bytes, manufacturer):
    """Extract metadata from PDF bytes given the manufacturer type.

    Returns a dict of extracted fields.
    """
    import PyPDF2
    import io

    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    text = reader.pages[0].extract_text()

    if manufacturer.lower() == 'cardiosoft':
        return extract_cardiosoft_metadata(text)
    elif manufacturer.lower() == 'schiller':
        return extract_schiller_metadata(text)
    else:
        raise ValueError(f'Unknown manufacturer: {manufacturer}')


# Canonical column order for ECG_records.csv
CSV_COLUMNS = [
    'filename',
    'patient_id',
    'name',
    'ecg_date',
    'ecg_time',
    'sex',
    'age',
    'birth_date',
    'ethnicity',
    'speed_mm_s',
    'duration',
    'available_leads',
    'heart_rate',
    'p_duration_ms',
    'pq_ms',
    'qrs_ms',
    'qt_ms',
    'qtc_ms',
    'rr_interval_ms',
    'pp_interval_ms',
    'p_axis',
    'qrs_axis',
    't_axis',
    'software_version',
    'device_model',
    'device_serial',
]
