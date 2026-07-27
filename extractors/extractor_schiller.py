"""
 Authors: Nils Gumpfer, Joshua Prim
 Version: 0.1

 Extractor for Schiller ECGs

 Copyright 2020 The Authors. All Rights Reserved.
"""
import io
import math
import sys
import numpy as np
import pandas as pd
import PyPDF2
from extractors.abstract_extractor import AbstractExtractor
from utils.data.visualisation import visualiseIndividualfromDF, visualiseIndividualinMPL
from utils.extract_utils.extract_utils import rotate_origin_only, move_along_the_axis, scale_values_based_on_eich_peak, \
    create_measurement_points, adjust_leads_baseline, extract_eichzacke_from_page_bytes, parse_schiller_waveforms
from utils.misc.datastructure import perform_shape_switch
from utils.metadata.extract_metadata import extract_schiller_metadata, CSV_COLUMNS
import logging
from tqdm import tqdm
import os

# Disable tqdm in frozen apps (PyInstaller) — stdout may be None/broken
_FROZEN = getattr(sys, 'frozen', False)


class SchillerExtractor(AbstractExtractor):

    def __init__(self, params):
        super().__init__(params)

        if 'ecg_path_source' not in self.params:
            raise ValueError('ecg_path_source is not set in params')
        else:
            self.path_source = params['ecg_path_source']

        if 'ecg_path_sink' not in self.params:
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

        # name of the leads
        self.lead_names = ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']

    def extract(self):
        records = []
        all_files = sorted(os.listdir(self.path_source))
        if self.filenames:
            all_files = [f for f in all_files if f in self.filenames]
        for file_name in tqdm(all_files, disable=_FROZEN):
            if not file_name.endswith('.pdf'):
                continue
            logging.info('Converting "{}"'.format(file_name))
            try:
                lead_list, gamma, meta = self.extract_leads_from_pdf(file_name)

                if lead_list is not None:
                    new_lead_list = []

                    for lead in lead_list:
                        tmp_lead = []

                        # Preprocess extracted vectors
                        for t in lead:
                            x, y = rotate_origin_only(float(t[0]), float(t[1]), math.radians(0))
                            tmp_lead.append([x, y])

                        new_lead = move_along_the_axis(tmp_lead)

                        # Scale values based on per-PDF Eichzacke calibration
                        new_lead = scale_values_based_on_eich_peak(new_lead, gamma)

                        # Create (e.g. 5000) measurement points based on the unevenly distributed points
                        measurement_points = create_measurement_points(new_lead, self.number_of_points)

                        # Collect converted leads
                        new_lead_list.append(measurement_points)

                    # Convert lead list to dataframe
                    df_leads = pd.DataFrame(perform_shape_switch(new_lead_list), columns=self.lead_names)

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

        return True

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

        # Extract metadata from first page text
        meta = extract_schiller_metadata(reader.pages[0].extract_text())

        num_pages = len(reader.pages)
        def _get_page_bytes(pg):
            c = pg.get_contents()
            if c is None:
                raise Exception('Page has no content stream (empty or corrupted page)')
            if isinstance(c, list):
                if not c or c[0] is None:
                    raise Exception('Page content stream list is empty or contains None')
                return c[0].get_data()
            return c.get_data()

        # Schiller: 2 pages of waveforms (page 0+1 for 2-page PDFs, page 1+2 for 3-page)
        if num_pages == 3:
            pg1_raw = _get_page_bytes(reader.pages[1])
            pg2_raw = _get_page_bytes(reader.pages[2])
        else:
            pg1_raw = _get_page_bytes(reader.pages[0])
            pg2_raw = _get_page_bytes(reader.pages[1])

        # Dynamically extract Eichzacke calibration from first page (raw bytes)
        eichzacke_span = extract_eichzacke_from_page_bytes(pg1_raw, manufacturer='schiller')
        if eichzacke_span and eichzacke_span > 10:
            gamma = self.eich_ref / eichzacke_span
            logging.info('Extracted Eichzacke span=%.3f → gamma=%.6f for %s',
                         eichzacke_span, gamma, filename)
        else:
            raise Exception(
                'Could not extract Eichzacke calibration square from Schiller PDF graphics. '
                'Check that the PDF contains a standard Schiller calibration mark.'
            )

        # Parse waveforms directly from raw path operators (no Q/C blocks in Schiller)
        leads1 = parse_schiller_waveforms(pg1_raw)
        leads2 = parse_schiller_waveforms(pg2_raw)
        leads = list(leads1) + list(leads2)

        if len(leads) != 12:
            raise Exception(
                f'Expected 12 Schiller waveform segments, got {len(leads)}. '
                f'Page1={len(leads1)}, Page2={len(leads2)}.'
            )

        # Validate point counts (Schiller waveforms are ~715 pts each)
        for i, lead in enumerate(leads):
            if len(lead) < 500 or len(lead) > 1500:
                raise Exception(
                    f'Lead {i} has {len(lead)} points (expected 500-1500). '
                    f'Segment may be malformed.'
                )

        return leads, gamma, meta

if __name__ == '__main__':
    path_source = '../data/pdf_data/pdf_schiller/original_ecgs/'
    path_sink = '../data/pdf_data/pdf_schiller/extracted_ecgs/'

    params = {
        'ecg_path_sink': path_sink,
        'ecg_path_source': path_source,
        'number_of_points': 5000,
        'show_visualisation': True,
    }

    tmp = SchillerExtractor(params)
    tmp.extract()
