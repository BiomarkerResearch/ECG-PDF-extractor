import numpy as np


def scale_ecg(ecg, factor):
    """
    Scales an ECG by a scaling factor and adjusts the unit of measurement accordingly.
    :param ecg: ECG containing multiple leads
    :param factor: a scaling value
    :return: an ECG scaled by the factor
    """
    for lead_id in ecg['leads']:
        lead = np.array(ecg['leads'][lead_id])
        ecg['leads'][lead_id] = lead * factor

    if factor == 1 / 1000 and ecg['metadata']['unitofmeasurement'] == 'uV':
        ecg['metadata']['unitofmeasurement'] = 'mV'
    else:
        ecg['metadata']['unitofmeasurement'] = ecg['metadata']['unitofmeasurement'] + '*' + str(factor)

    return ecg


def scale_ecgs(ecgs, factor):
    """
    Scales a list of ECGs by a scaling factor.
    :param ecgs: list of ECGs
    :param factor: a scaling value
    :return: a list of ECGs scaled by the factor
    """
    scaled_ecgs = {}

    for record_id in ecgs:
        scaled_ecgs[record_id] = scale_ecg(ecgs[record_id], factor)

    return scaled_ecgs


def derive_ecg_variants_multi(ecgs, variants):
    """
    Converts a list of ECGs to the same format, only containing absolute voltage numbers.
    :param ecgs: List of ECGs
    :param variants: possible formats
    :return: a list of ECGs with absolute voltage values
    """
    derived_ecgs = {}

    for record_id in ecgs:
        derived_ecgs[record_id] = derive_ecg_variants(ecgs[record_id], variants)

    return derived_ecgs


def calculate_delta_for_lead(lead):
    """
    Converts a lead that is recorded as delta values into a lead with absolute values.
    :param lead: a lead with delta voltage values
    :return: a lead with absolute voltage values
    """
    delta_list = []

    for index in range(0, len(lead) - 1):
        delta_list.append(lead[index + 1] - lead[index])

    delta_list = np.round(np.array(delta_list), 6)

    return delta_list


def calculate_delta_for_leads(leads):
    """
    Converts leads recorded as delta values into leads with absolute values.
    :param leads: leads with delta voltage values
    :return: leads with absolute voltage values
    """
    delta_leads = {}

    for lead_id in leads:
        delta_leads[lead_id] = calculate_delta_for_lead(leads[lead_id])

    return delta_leads


def derive_ecg_variants(ecg, variants):
    """
    Converts an ecg to a format, containing absolute voltage numbers.
    :param ecg: an ECG
    :param variants: possible formats
    :return: an ECG with absolute voltage values
    """
    derived_ecg = {}
    for variant in variants:
        if variant == 'ecg_raw':
            derived_ecg[variant] = ecg['leads']
        elif variant == 'ecg_delta':
            derived_ecg[variant] = calculate_delta_for_leads(ecg['leads'])

    derived_ecg['metadata'] = ecg['metadata']

    return derived_ecg


def combine_ecgs_and_clinical_parameters(ecgs, clinical_parameters):
    """
    Combines ECGs and their corresponding clinical parameters.
    :param ecgs: List of ECGs
    :param clinical_parameters: Corresponding clinical parameters
    :return: Medical data for each patient including ECGs and the patients clinical parameters
    """
    combined = {}

    for record_id in ecgs:
        ecg = ecgs[record_id]

        try:
            cp = clinical_parameters[record_id]
        except KeyError:
            continue

        combined[record_id] = dict(ecg)
        combined[record_id].update(cp)

    return combined
