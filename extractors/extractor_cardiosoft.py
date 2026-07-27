"""
 Authors: Nils Gumpfer, Joshua Prim
 Version: 0.1

 Extractor for Cardiosoft ECGs

 Copyright 2020 The Authors. All Rights Reserved.
"""
import io
import os
import math
import numpy as np
import pandas as pd
import PyPDF2

from extractors.abstract_extractor import AbstractExtractor
from utils.extract_utils.extract_utils import rotate_origin_only, move_along_the_axis, scale_values_based_on_eich_peak, \
    create_measurement_points, adjust_leads_baseline, preprocess_page_content, extract_graphics_string, \
    extract_eichzacke_from_page_bytes, clip_preamble_points
from utils.misc.datastructure import perform_shape_switch
from utils.data.visualisation import visualiseIndividualfromDF, visualiseIndividualinMPL
from utils.metadata.extract_metadata import extract_cardiosoft_metadata, CSV_COLUMNS
from tqdm import tqdm
import logging


class CardiosoftExtractor(AbstractExtractor):

    def __init__(self, params):
        super().__init__(params)

        if 'ecg_path_source' not in params:
            raise ValueError('ecg_path_source is not set in params')
        else:
            self.path_source = params['ecg_path_source']

        if 'ecg_path_sink' not in params:
            raise ValueError('ecg_path_sink is not set in params')
        else:
            self.path_sink = params['ecg_path_sink']
        # reference value for the calibration jag (1 mV = 1000 uV)
        self.eich_ref = 1000

        if 'number_of_points' not in params:
            raise ValueError('number_of_points is not set in params')
        else:
            # number of measuring points in XML
            self.number_of_points = params['number_of_points']

        if 'show_visualisation' in params:
            self.show_visualisation = params['show_visualisation']
        else:
            self.show_visualisation = False

        if 'vis_scale' in params:
            self.vis_scale = params['vis_scale']
        else:
            self.vis_scale = 1

        if 'vis_MPL' in params:
            self.vis_MPL = params['vis_MPL']
        else:
            self.vis_MPL = False

        if 'version' not in params:
            self.version = '6.5'
        else:
            self.version = params['version']

    def extract(self):
        records = []
        all_files = sorted(os.listdir(self.path_source))
        if self.filenames:
            all_files = [f for f in all_files if f in self.filenames]
        for file_name in tqdm(all_files):
            if not file_name.endswith('.pdf'):
                continue
            logging.info('Converting "{}"'.format(file_name))
            try:
                # Extract leads + metadata from PDF (gamma is computed per-PDF from Eichzacke)
                lead_list, lead_ids, record_id, gamma, meta = self.extract_leads_from_pdf(file_name)

                if lead_list is not None:
                    # Determine rotation angle from detected waveform orientation
                    orientation = getattr(self, '_page_orientation', 'vertical')
                    rotation_angle = math.radians(90) if orientation == 'vertical' else math.radians(0)
                    logging.info('PDF %s: orientation=%s, rotation=%.0f°', file_name, orientation, math.degrees(rotation_angle))

                    new_lead_list = []

                    for lead in lead_list:
                        tmp_lead = []

                        # Preprocess extracted vectors with orientation-aware rotation
                        for t in lead:
                            x, y = rotate_origin_only(float(t[0]), float(t[1]), rotation_angle)
                            tmp_lead.append([x, y])

                        new_lead = move_along_the_axis(tmp_lead)

                        # Scale values based on per-PDF Eichzacke calibration
                        new_lead = scale_values_based_on_eich_peak(new_lead, gamma)

                        # Create (e.g. 5000) measurement points based on the unevenly distributed points
                        measurement_points = create_measurement_points(new_lead, self.number_of_points)

                        # Collect converted leads
                        new_lead_list.append(measurement_points)

                    # Convert lead list to dataframe
                    df_leads = pd.DataFrame(perform_shape_switch(new_lead_list), columns=lead_ids)

                    # Adjust baseline position of each lead
                    df_leads = adjust_leads_baseline(df_leads)

                    # Plot leads of ECG if config is set to do so
                    if self.show_visualisation:
                        if not self.vis_MPL:
                            visualiseIndividualfromDF(df_leads, self.vis_scale)
                        else:
                            visualiseIndividualinMPL(df_leads)

                    out_path = os.path.join(self.path_sink, file_name.replace('.pdf', '') + '.csv')
                    df_leads.to_csv(out_path,
                                    index=False)

                    # Collect metadata record for consolidated CSV
                    meta['filename'] = file_name
                    records.append(meta)
                else:
                    logging.error('Lead list is none')
            except Exception as e:
                logging.warning('Failed to extract %s: %s', file_name, str(e))

        # Write consolidated ECG_records.csv
        if records:
            self._write_ecg_records(records)

    def _write_ecg_records(self, records):
        """Write consolidated ECG_records.csv alongside the extracted CSV files."""
        df = pd.DataFrame(records, columns=CSV_COLUMNS)
        sink_dir = self.path_sink.rstrip('/')
        out_path = os.path.join(sink_dir, 'ECG_records.csv')
        df.to_csv(out_path, index=False)
        logging.info('Wrote %d records to %s', len(df), out_path)

    def extract_leads_from_pdf(self, filename):
        filepath = os.path.join(self.path_source, filename)
        with open(filepath, 'rb') as f:
            data = f.read()
        reader = PyPDF2.PdfReader(io.BytesIO(data))

        try:
            leads = []
            lead_ids = []
            record_id = None
            gamma = None
            meta = {}
            self._page_orientation = ['vertical']  # default per-file

            for p in range(len(reader.pages)):
                if len(leads) == 12:
                    break

                page = reader.pages[p]
                text = page.extract_text()

                is_cover_page = text.startswith('Page') or text.startswith('Seite')

                if not is_cover_page:

                    self.get_version(text)

                    # Extract metadata from first valid page only
                    if p == 0 or (not leads and not meta):
                        meta = extract_cardiosoft_metadata(text)

                    contents = page.get_contents()
                    if isinstance(contents, list):
                        page_content_bytes = contents[0].get_data()
                    else:
                        page_content_bytes = contents.get_data()

                    page_content = preprocess_page_content(page_content_bytes)
                    graphics_string = extract_graphics_string(page_content)

                    # Dynamically extract Eichzacke calibration square dimensions from first valid page
                    if gamma is None:
                        eichzacke_span = extract_eichzacke_from_page_bytes(page_content_bytes, manufacturer='cardiosoft')
                        if eichzacke_span and eichzacke_span > 10:
                            gamma = self.eich_ref / eichzacke_span
                            logging.info('Extracted Eichzacke Y span=%.3f → gamma=%.6f for %s',
                                         eichzacke_span, gamma, filename)
                        else:
                            raise Exception(
                                'Could not extract Eichzacke calibration square from PDF graphics. '
                                'Check that the PDF contains a standard Cardiosoft calibration mark.'
                            )

                    page_leads, orientation = self.extract_leads_from_page_content(graphics_string)
                    # Clip preamble points per-page (orientation-aware: vertical→Y, horizontal→X)
                    page_leads = clip_preamble_points(page_leads, orientation=orientation)
                    leads.extend(page_leads)
                    lead_ids += self.extract_lead_ids(text)
                    record_id = self.extract_record_id(text)

                    # Store orientation for rotation (first valid page determines it)
                    if not isinstance(getattr(self, '_page_orientation', None), str):
                        self._page_orientation = orientation


                else:
                    logging.info('Skipping cover page (page {})'.format(p))

            if len(leads) != 12:
                raise Exception('Invalid ECG with {} leads'.format(len(leads)))

            if gamma is None:
                raise Exception('No valid page found to extract Eichzacke calibration')

        except Exception as e:
            logging.error('Could not convert "{}": '.format(filename, e))
            leads = None
            lead_ids = None
            record_id = None
            gamma = None
            meta = {}

        return leads, lead_ids, record_id, gamma, meta

    def extract_lead_ids(self, pagetext):
        import re
        lines = pagetext.split('\n')

        # Filter out PDF rendering artifacts (lines of repeated single chars > 50 length)
        clean_lines = [l for l in lines if len(l) <= 50 or len(set(l.strip())) > 1]

        lead_ids = clean_lines[-6:]

        # Strip leading/trailing repeated single characters from each ID (PDF artifact cleanup)
        # Only strip if 5+ repetitions to avoid removing legitimate "III" etc.
        lead_ids = [re.sub(r'^(.)\1{4,}', '', lid).strip() for lid in lead_ids]

        if len(lead_ids) >= 2 and lead_ids[1].strip() == 'III':
            lead_ids[0] = 'I'
            lead_ids[1] = 'II'

        # Handle Cardiosoft variant where first lead ID is embedded in a grid line
        # (e.g., "111...I" or "111...V1") and gets filtered out by the length check.
        # Detect by looking for long lines that end with a valid lead identifier.
        if len(lead_ids) < 6:
            embedded = []
            for line in lines:
                m = re.match(r'^(.)\1{20,}(.+)$', line.strip())
                if m:
                    suffix = m.group(2).strip()
                    if suffix in ('I', 'II', 'III', 'aVR', 'aVL', 'aVF',
                                  'V1', 'V2', 'V3', 'V4', 'V5', 'V6'):
                        embedded.append(suffix)

            missing = list(dict.fromkeys(s for s in embedded if s not in lead_ids))
            needed = 6 - len(lead_ids)
            lead_ids = missing[:needed] + lead_ids

        if len(lead_ids) != 6:
            logging.warning('Expected 6 lead IDs per page, got %d', len(lead_ids))

        return [lid.strip() for lid in lead_ids]

    def get_version(self, pagetext):
        lines = pagetext.split('\n')

        version_lines = []

        for element in lines:
            if 'GE CardioSoft' in element or 'GE CASE' in element:
                version_lines.append(element)

        if not version_lines:
            self.version = '6.5'
            return

        vline = version_lines[0]
        if 'V6.73' in vline:
            self.version = '6.73'
        elif 'V6.0' in vline:
            self.version = '6.0'
        else:
            self.version = '6.5'

    def extract_record_id(self, pagetext):
        lines = pagetext.split('\n')
        record_id = None

        for i in range(len(lines)):
            line = lines[i]

            if line.startswith('Patient'):
                parts = line.split(':')
                number = parts[1].replace(' ', '')
                date = lines[i + 2].replace('.', '-')
                time = lines[i + 4].replace(':', '-')

                record_id = '{}_{}_{}'.format(number, date, time)

                break

        return record_id

    def extract_leads_from_page_content(self, graphics_string):
        """Extract lead waveforms from Q-segments.

        Returns (leads, orientation) where orientation is 'vertical' or 'horizontal'.
        Vertical: Y span >> X span per segment (needs 90° rotation).
        Horizontal: X span >> Y span per segment (no rotation needed).
        """
        leads = []

        if float(self.version) < 6.5:
            cutting_range = [7, 13]
        else:
            cutting_range = [8, 14]

        for i in range(cutting_range[0], cutting_range[1]):
            if i >= len(graphics_string):
                break

            seg = graphics_string[i]
            lead = []

            # Parse coordinates line-by-line (no split('S') — robust against embedded 'S' chars)
            for line in seg.split('\n'):
                parts = line.strip().split()
                if len(parts) == 2:
                    try:
                        x, y = float(parts[0]), float(parts[1])
                        # Filter out extreme outliers (grid lines, page margins)
                        lead.append([x, y])
                    except ValueError:
                        pass

            lead = np.array(lead)
            if len(lead) > 50:
                leads.append(lead)

        # Detect orientation from first valid lead segment
        orientation = 'vertical'  # default
        if leads is not None and len(leads) > 0:
            xs = leads[0][:, 0]
            ys = leads[0][:, 1]
            x_span = max(xs) - min(xs)
            y_span = max(ys) - min(ys)
            if x_span > y_span:
                orientation = 'horizontal'

        return leads, orientation


if __name__ == '__main__':
    path_source = '../data/pdf_data/pdf_cardiosoft/original_ecgs/'
    path_sink = '../data/pdf_data/pdf_cardiosoft//extracted_ecgs/'

    params = {
        'ecg_path_source': path_source,
        'ecg_path_sink': path_sink,
        'number_of_points': 5000,
        'show_visualisation': True,
    }

    tmp = CardiosoftExtractor(params)
    tmp.extract()

