import os
import sys
import logging
import pandas as pd
import configparser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data.data import scale_ecgs, derive_ecg_variants_multi, \
    combine_ecgs_and_clinical_parameters
from extractors.extractor_schiller import SchillerExtractor
from extractors.extractor_cardiosoft import CardiosoftExtractor
from utils.metadata.extract_metadata import detect_manufacturer
from utils.data.visualisation import visualiseMulti
from utils.file.file import checkpathsandmake


class ExecutionRunner:
    def __init__(self, config_path=None, path_source=None, path_sink=None):

        config = configparser.ConfigParser()
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config.ini',
            )
        read_ok = config.read(config_path)

        if len(read_ok) == 0:
            raise Exception(f'Could not read config file at {config_path}.')

        self.initialize_logger(loglevel='WARNING')

        self.IS_PDf = config['pdf'].getboolean('is_pdf')
        self.new_extraction = config['pdf'].getboolean('override')

        self.vis_while_extraction = config['pdf'].getboolean('vis_while_extraction')
        self.vis_with_MPL = config['pdf'].getboolean('vis_with_MatplotLib')
        self.vis_after_extraction = config['pdf'].getboolean('vis_after_extraction')
        self.vis_scale = config['pdf'].getfloat('vis_scale')

        self.manufacturer = config['pdf'].get('manufacturer')
        if self.manufacturer == "schiller":
            self.manufacturer = "Schiller"
        if self.manufacturer == "cardiosoft":
            self.manufacturer = "Cardiosoft"

        self.leads_to_use = config['pdf'].get('leads_to_use')
        self.record_ids_excluded = ''

        self.seconds = int(config['pdf'].get('seconds'))

        # Optional path overrides (used by the GUI)
        self.path_source_override = path_source
        self.path_sink_override = path_sink
        self.hz = 500

    def initialize_logger(self, loglevel='INFO'):

        consolehandler = logging.StreamHandler(sys.stdout)

        formatter = logging.Formatter('%(asctime)-15s %(levelname)s %(message)s')
        consolehandler.setFormatter(formatter)

        log = logging.getLogger()

        for hdlr in log.handlers[:]:
            log.removeHandler(hdlr)
        log.addHandler(consolehandler)
        log.setLevel(loglevel)

    def load_csv(self, path_csv):
        f = []
        for (dirpath, dirnames, filenames) in os.walk(path_csv):
            f.extend(filenames)
            break

        ecg_dict = {}

        for file_name in f:
            if not file_name.endswith('.csv'):
                continue
            # Skip ECG_records.csv — it's metadata, not waveform data
            if file_name == 'ECG_records.csv':
                continue

            ecg_df = pd.read_csv(os.path.join(path_csv, file_name))
            ecg_df = ecg_df.astype('int32')

            record_id = file_name.replace(".csv", "")
            tmp_dict = {}

            for column in ecg_df:
                ecg_list = ecg_df[column].tolist()
                tmp_dict[column] = ecg_list

            tmp_dict2 = {}
            tmp_dict2['leads'] = tmp_dict
            tmp_dict2['metadata'] = {'sampling_rate_sec': 500, 'unitofmeasurement': 'uV', 'length_sec': 10,
                                     'length_timesteps': 5000}

            ecg_dict[record_id] = tmp_dict2

        return ecg_dict

    def load_ecg_records_metadata(self, path_sink):
        """Load consolidated ECG_records.csv written by the extractor."""
        sink_dir = path_sink.rstrip('/')
        records_path = os.path.join(sink_dir, 'ECG_records.csv')
        if not os.path.exists(records_path):
            raise FileNotFoundError(
                f'ECG_records.csv not found at {records_path}. '
                f'Run extraction first (set override=true in config.ini).'
            )
        df = pd.read_csv(records_path)
        logging.info('Loaded %d metadata records from ECG_records.csv', len(df))
        return df

    def _detect_all_manufacturers(self, path_source):
        """Scan all PDFs and return {filename: manufacturer} dict."""
        detection = {}
        for fname in sorted(os.listdir(path_source)):
            if not fname.endswith('.pdf'):
                continue
            fpath = os.path.join(path_source, fname)
            with open(fpath, 'rb') as f:
                pdf_bytes = f.read()
            mfr = detect_manufacturer(pdf_bytes)
            detection[fname] = mfr or 'Unknown'
        return detection

    def _run_extractor(self, manufacturer, path_source, path_sink, filenames=None):
        """Run the appropriate extractor for a group of PDFs."""
        params = {
            'ecg_path_source': path_source,
            'ecg_path_sink': path_sink,
            'number_of_points': self.seconds * self.hz,
            'show_visualisation': self.vis_while_extraction,
            'vis_scale': self.vis_scale,
            'vis_MPL': self.vis_with_MPL,
        }
        if filenames:
            params['filenames'] = set(filenames)

        if manufacturer == 'Schiller':
            ext = SchillerExtractor(params)
            ext.extract()
            logging.info('Schiller PDF extraction successful (%d files)', len(filenames))
        elif manufacturer == 'Cardiosoft':
            ext = CardiosoftExtractor(params)
            ext.extract()
            logging.info('CardioSoft PDF extraction successful (%d files)', len(filenames))

    def pre_processing(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 1. Load ECGs
        logging.info('Loaded ECGs from snapshot')

        if self.IS_PDf:
            path_source = (
                self.path_source_override
                if self.path_source_override
                else os.path.join(base_dir, 'data', 'pdf_data', 'pdf_schiller', 'original_ecgs')
            )
            path_sink = (
                self.path_sink_override
                if self.path_sink_override
                else os.path.join(base_dir, 'data', 'pdf_data', 'pdf_schiller', 'extracted_ecgs')
            )

            checkpathsandmake(path_sink)
            checkpathsandmake(path_source)

            # Auto-detect mode: scan all PDFs, group by manufacturer, extract each group
            if self.manufacturer == 'Auto':
                logging.info('Auto-detecting manufacturers …')
                detection = self._detect_all_manufacturers(path_source)

                groups = {'Schiller': [], 'Cardiosoft': [], 'Unknown': []}
                for fname, mfr in detection.items():
                    groups[mfr].append(fname)

                logging.info(
                    'Detection: Schiller=%d, Cardiosoft=%d, Unknown=%d',
                    len(groups['Schiller']),
                    len(groups['Cardiosoft']),
                    len(groups['Unknown']),
                )

                if self.new_extraction:
                    for mfr in ('Schiller', 'Cardiosoft'):
                        if groups[mfr]:
                            self._run_extractor(mfr, path_source, path_sink, groups[mfr])

                if groups['Unknown']:
                    logging.warning(
                        '%d file(s) could not be auto-detected: %s',
                        len(groups['Unknown']), groups['Unknown'],
                    )

            elif self.manufacturer == 'Schiller':
                params = {
                    'ecg_path_sink': path_sink,
                    'ecg_path_source': path_source,
                    'number_of_points': self.seconds * self.hz,
                    'show_visualisation': self.vis_while_extraction,
                    'vis_scale': self.vis_scale,
                    'vis_MPL': self.vis_with_MPL,
                }

                if self.new_extraction:
                    schillerExtractor = SchillerExtractor(params)
                    schillerExtractor.extract()
                    logging.info('Schiller PDF extraction successful')
                else:
                    logging.warning('Please note that no new extraction is performed.')

            elif self.manufacturer == 'Cardiosoft':
                params = {
                    'ecg_path_source': path_source,
                    'ecg_path_sink': path_sink,
                    'number_of_points': self.seconds * self.hz,
                    'show_visualisation': self.vis_while_extraction,
                    'vis_scale': self.vis_scale,
                    'vis_MPL': self.vis_with_MPL,
                }

                if self.new_extraction:
                    cardiosoftExtractor = CardiosoftExtractor(params)
                    cardiosoftExtractor.extract()
                    logging.info('CardioSoft PDF extraction successful')
                else:
                    logging.warning('Please note that no new extraction is performed.')

            original_ecgs = self.load_csv(path_csv=path_sink)
        else:
            raise Exception('Non-PDF path not supported. Set is_pdf=True in config.ini.')

        # Visualise Extracted ECGs
        if self.vis_after_extraction:
            visualiseMulti(original_ecgs, self.vis_scale)

        # 2. Scale ECGs
        logging.info('Scaled ECGs')
        scaled_ecgs = scale_ecgs(original_ecgs, 1 / 1000)

        # 3. Further ECG derivation
        logging.info('Derived further ECG variants')
        derived_ecgs = derive_ecg_variants_multi(scaled_ecgs, ['ecg_raw'])

        # 4. Load clinical metadata from ECG_records.csv (extracted directly from PDFs)
        if self.IS_PDf and path_sink:
            logging.info('Load clinical metadata from ECG_records.csv')
            ecg_records_df = self.load_ecg_records_metadata(path_sink)

            # Build clinical_parameters dict keyed by record_id for combine_ecgs_and_clinical_parameters
            clinical_params = {}
            for _, row in ecg_records_df.iterrows():
                # Record ID is the filename without .pdf extension
                record_id = row.get('filename', '').replace('.pdf', '')
                if not record_id:
                    continue

                # Build a flat dict of available metadata fields as clinical parameters
                params_dict = {}
                for col in ecg_records_df.columns:
                    if col == 'filename':
                        continue
                    val = row.get(col)
                    if pd.isna(val):
                        continue
                    params_dict[col] = val

                clinical_params[record_id] = {'clinical_parameters_inputs': params_dict}

            # Combine ECGs with clinical metadata
            logging.info('Combined ECGs and clinical parameters')
            combined_records = combine_ecgs_and_clinical_parameters(derived_ecgs, clinical_params)

        else:
            # Fallback for non-PDF path (XML-based): keep original behavior placeholder
            logging.warning('Non-PDF path not yet implemented with new metadata pipeline.')
            combined_records = derived_ecgs

        return combined_records

    def run(self):
        """Main entry point: execute pre-processing pipeline."""
        return self.pre_processing()

    @staticmethod
    def bootstrap():
        exr = ExecutionRunner()
        try:
            exr.run()
        except Exception as e:
            logging.error(str(e))
            raise Exception(e.args)


if __name__ == '__main__':
    exr = ExecutionRunner()
    try:
        exr.run()
    except Exception as e:
        logging.error(str(e))
        raise Exception(e.args)
