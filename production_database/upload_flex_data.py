'''
Script to upload flex data (.json file) to PDB.
'''
import json
import time
import logging
import coloredlogs

from itkprodDB_interface import ITkProdDB
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path

X_UPPER = 39.7
X_LOWER = 39.5
Y_UPPER = 40.7
Y_LOWER = 40.5

HV_CAP_LOWER = 1.701
HV_CAP_UPPER = 2.102

def _read_file(filename):
    ''' Read .json file and check if it contains required keys.
    '''
    d = open(filename).read()
    data = json.loads(d)

    return data

def _read_xlsx_file(xlsx_file, sheet_name):
    WS = pd.read_excel(io=xlsx_file, sheet_name=sheet_name, header=None)
    return np.array(WS)

def convert_flex_metrology_data(flex_metrology_data_file):
    outfile_json = flex_metrology_data_file[:-4] + '_flex_metrology.json'

    data = _read_xlsx_file(xlsx_file=flex_metrology_data_file, sheet_name=0)
    flex_sn = '20UPGPQ' + ''.join(data[2, 2].replace(' ', '-').split('-'))

    datetime_str = data[2, 6]
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    x_dim = round(data[33, 9], 3)
    y_dim = round(data[39, 9], 3)
    hv_cap_thickness = round(data[43, 4], 3)
    flex_thickness = round(data[33, 4]  / 1000.0, 3)  # in mm
    flex_thickness_std = round(np.std(data[30:34, 2])  / 1000.0, 4)  # in mm
    power_connector_thickness = round(data[48, 4], 3)

    x_y_dim_in_envelop = False
    if x_dim < X_UPPER and x_dim > X_LOWER and y_dim < Y_UPPER and y_dim > Y_LOWER:
        x_y_dim_in_envelop = True

    hv_cap_thickness_in_envelop = False
    if hv_cap_thickness < HV_CAP_UPPER and hv_cap_thickness > HV_CAP_LOWER:
        hv_cap_thickness_in_envelop = True

    json_string = {
            "component": flex_sn,
            "testType": "METROLOGY",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": x_y_dim_in_envelop & hv_cap_thickness_in_envelop,
            "problems": False,
            "properties": {
                "OPERATOR": "Wolfgang Dietsche",
                "INSTRUMENT": "Mitutoyo MF-UH1010TH",
                "ANALYSIS_VERSION": None},
            "results": {
                "X_DIMENSION": x_dim,
                "Y_DIMENSION": y_dim,
                "X-Y_DIMENSION_WITHIN_ENVELOP": x_y_dim_in_envelop,
                "AVERAGE_THICKNESS_FECHIP_PICKUP_AREAS": flex_thickness,
                "STD_DEVIATION_THICKNESS_FECHIP_PICKUP_AREAS": flex_thickness_std,
                "HV_CAPACITOR_THICKNESS_WITHIN_ENVELOP": hv_cap_thickness_in_envelop,
                "HV_CAPACITOR_THICKNESS": hv_cap_thickness,
                "AVERAGE_THICKNESS_POWER_CONNECTOR":power_connector_thickness,
                "DIAMETER_DOWEL_HOLE_A": None,
                "WIDTH_DOWEL_SLOT_B": None }
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json

def convert_flex_mass_data(flex_mass_data_file):
    outfile_json = flex_mass_data_file[:-4] + '_flex_mass.json'

    data = _read_xlsx_file(xlsx_file=flex_mass_data_file, sheet_name=0)
    flex_sn = '20UPGPQ' + ''.join(data[2, 2].replace(' ', '-').split('-'))

    datetime_str = data[2, 6]
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    flex_mass = round(data[27, 7], 3) * 1000.0  # in mg

    json_string = {
            "component": flex_sn,
            "testType": "MASS",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": True,
            "problems": False,
            "properties": {
                "OPERATOR": "Wolfgang Dietsche",
                "INSTRUMENT": "Mitutoyo MF-UH1010TH",
                "ANALYSIS_VERSION": None},
            "results": {
                "MASS": flex_mass}
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json


def convert_flex_vi_data(flex_mass_data_file):
    outfile_json = flex_mass_data_file[:-4] + '_flex_VI.json'

    data = _read_xlsx_file(xlsx_file=flex_mass_data_file, sheet_name=0)
    flex_sn = '20UPGPQ' + ''.join(data[2, 2].replace(' ', '-').split('-'))

    datetime_str = data[2, 6]
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    WIREBOND_PADS_CONTAMINATION_GRADE = data[53, 13]
    PARTICULATE_CONTAMINATION_GRADE = data[54, 13]
    WATERMARKS_GRADE = data[55, 13]
    SCRATCHES_GRADE = data[56, 13]
    SOLDERMASK_IRREGULARITIES_GRADE = data[57, 13]
    HV_LV_CONNECTOR_ASSEMBLY_GRADE = data[58, 13]
    DATA_CONNECTOR_ASSEMBLY_GRADE = data[59, 13]
    SOLDER_SPILLS_GRADE = data[60, 13]
    COMPONENT_MISALIGNMENT_GRADE = data[61, 13]
    SHORTS_OR_CLOSE_PROXIMITY_GRADE = data[62, 13]
    OVERALL_GRADE = data[63, 13]
    OBSERVATION = str(data[64, 13])

    if OBSERVATION == 'nan':
        OBSERVATION = ''

    json_string = {
            "component": flex_sn,
            "testType": "VISUAL_INSPECTION",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": True,
            "problems": False,
            "properties": {
                "OPERATOR": "Wolfgang Dietsche",
                "INSTRUMENT": "Mitutoyo MF-UH1010TH",
                "ANALYSIS_VERSION": None},
            "results":{
                "WIREBOND_PADS_CONTAMINATION_GRADE": int(WIREBOND_PADS_CONTAMINATION_GRADE),
                "PARTICULATE_CONTAMINATION_GRADE": int(PARTICULATE_CONTAMINATION_GRADE),
                "WATERMARKS_GRADE": int(WATERMARKS_GRADE),
                "SCRATCHES_GRADE": int(SCRATCHES_GRADE),
                "SOLDERMASK_IRREGULARITIES_GRADE": int(SOLDERMASK_IRREGULARITIES_GRADE),
                "HV_LV_CONNECTOR_ASSEMBLY_GRADE": int(HV_LV_CONNECTOR_ASSEMBLY_GRADE),
                "DATA_CONNECTOR_ASSEMBLY_GRADE": int(DATA_CONNECTOR_ASSEMBLY_GRADE),
                "SOLDER_SPILLS_GRADE": int(SOLDER_SPILLS_GRADE),
                "COMPONENT_MISALIGNMENT_GRADE": int(COMPONENT_MISALIGNMENT_GRADE),
                "SHORTS_OR_CLOSE_PROXIMITY_GRADE": int(SHORTS_OR_CLOSE_PROXIMITY_GRADE),
                "OVERALL_GRADE": int(OVERALL_GRADE),
                "OBSERVATION": OBSERVATION
                }
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json

def upload_flex_data(flex_metrology_data_json=None, flex_mass_data_json=None, flex_vi_data_json=None, flex_vi_pictures=None):
    ''' Upload flex data
    '''
    with ITkProdDB() as itk_prodDB:
        if flex_metrology_data_json is not None:
            data = _read_file(flex_metrology_data_json)
            itk_prodDB.upload_flex_data(data)
        if flex_mass_data_json is not None:
            data = _read_file(flex_mass_data_json)
            itk_prodDB.upload_flex_data(data)
        if flex_vi_data_json is not None:
            itk_prodDB.upload_flex_data(data, filename, filename_data)
            for k, filename in enumerate(flex_vi_pictures):
                if k == 0:
                    side = "frontside"
                if k == 1:
                    side = "frontside"
                elif:
                    raise RuntimeError('To many VI pictures specified!')
                data = _read_file(flex_vi_data_json)
                filename_data = {"testRun": None, # will be set later when test run ID is know
                        "title": "{0} {1}".format(data['component'], side),
                        "description": "{0} {1}".format(data['component'], side),
                        "url": Path(filename),
                        "type": "file"}


if __name__ == "__main__":
    flex_data_files = [ "/home/yannick/Downloads/ITk  Flex 78 18.01.2024.xls",
                      ]

    flex_vi_pictures = ["/home/yannick/Downloads/Flex 078.JPG", "/home/yannick/Downloads/Flex 078_B.JPG"]  # front back

    # convert and upload data
    for flex_data_file in flex_data_files:
        # extract metrology, mass and VI
        flex_metrology_data_json = convert_flex_metrology_data(flex_data_file)
        flex_mass_data_json = convert_flex_mass_data(flex_data_file)
        flex_vi_data_json = convert_flex_vi_data(flex_data_file)
        # upload
        upload_flex_data(flex_metrology_data_json=flex_metrology_data_json,
                         flex_mass_data_json=flex_mass_data_json,
                         flex_vi_data_json=flex_vi_data_json,
                         flex_vi_pictures=flex_vi_pictures)
