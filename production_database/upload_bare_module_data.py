'''
Script to upload bare module data (.json file) to PDB.
'''
import json
import time
import logging
import coloredlogs
import pandas as pd
import numpy as np
from datetime import datetime

from pathlib import Path

from itkprodDB_interface import ITkProdDB


X_FE_UPPER = 42.187 + 0.07
X_FE_LOWER = 42.187
Y_FE_UPPER = 40.255 + 0.07
Y_FE_LOWER = 40.255

FE_THICKNESS_UPPER = 150.0 + 25
FE_THICKNESS_LOWER = 150.0 - 10

X_SENSOR_UPPER = 39.5 + 0.05
X_SENSOR_LOWER = 39.5
Y_SENSOR_UPPER = 41.1 + 0.05
Y_SENSOR_LOWER = 41.1

MOD_THICKNESS_UPPER = 325 + 90
MOD_THICKNESS_LOWER = 325 - 40

def _read_file(filename):
    ''' Read .json file and check if it contains required keys.
    '''
    d = open(filename).read()
    data = json.loads(d)

    return data

def _read_xlsx_file(xlsx_file, sheet_name):
    WS = pd.read_excel(io=xlsx_file, sheet_name=sheet_name, header=None)
    return np.array(WS)

def convert_bare_module_metrology_data(bare_module_metrology_data_file):
    outfile_json = bare_module_metrology_data_file[:-4] + '_bare_module_metrology.json'

    data = _read_xlsx_file(xlsx_file=bare_module_metrology_data_file, sheet_name=0)
    bare_module_sn = '20UPG' + ''.join(data[6, 2].replace(' ', '-').split('-'))

    datetime_str = data[6, 6]
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    sensor_x = round(np.mean(data[30:32, 7]), 3)
    sensor_y = round(np.mean(data[33:35, 7]), 3)
    sensor_thickness = None  # not really needed
    sensor_thickness_std = None  # not really needed
    fe_x = round(np.mean(data[27:29, 7]), 3)
    fe_y = round(np.mean(data[36:38, 7]), 3)
    fe_thickness = int(np.mean(data[40:44, 9]))
    fe_thickness_std = int(np.std(data[40:44, 9]))
    bare_module_thickness = int(data[30, 4])
    bare_module_thickness_std = int(np.std(data[27:31, 2]))

    fe_dim_in_envelop = False
    if (fe_x < X_FE_UPPER) and (fe_x > X_FE_LOWER) and (fe_y < Y_FE_UPPER) and (fe_y > Y_FE_LOWER) and (fe_thickness < FE_THICKNESS_UPPER) and (fe_thickness > FE_THICKNESS_LOWER):
        fe_dim_in_envelop = True

    sensor_dim_in_envelop = False
    if (sensor_x < X_FE_UPPER) and (sensor_x > X_SENSOR_LOWER) and (sensor_y < Y_SENSOR_UPPER) and (sensor_y > Y_SENSOR_LOWER):
        sensor_dim_in_envelop = True

    mod_dim_in_envelop = False
    if bare_module_thickness < MOD_THICKNESS_UPPER and bare_module_thickness > MOD_THICKNESS_LOWER:
        mod_dim_in_envelop = True

    json_string = {
            "component": bare_module_sn,
            "testType": "QUAD_BARE_MODULE_METROLOGY",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": mod_dim_in_envelop & sensor_dim_in_envelop & fe_dim_in_envelop,
            "problems": False,
            "properties": {
                # "OPERATOR": "Wolfgang Dietsche",
                # "INSTRUMENT": "Mitutoyo MF-UH1010TH",
                "ANALYSIS_VERSION": None},
            "results":{
                "SENSOR_X": sensor_x,
                "SENSOR_Y": sensor_y,
                "SENSOR_THICKNESS": sensor_thickness,
                "SENSOR_THICKNESS_STD_DEVIATION": sensor_thickness_std,
                "FECHIPS_X": fe_x,
                "FECHIPS_Y": fe_y,
                "FECHIP_THICKNESS": fe_thickness, 
                "FECHIP_THICKNESS_STD_DEVIATION": fe_thickness_std,
                "BARE_MODULE_THICKNESS": bare_module_thickness,
                "BARE_MODULE_THICKNESS_STD_DEVIATION": bare_module_thickness_std}
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)
    
    return outfile_json

def convert_bare_module_mass_data(bare_module_mass_data_file):
    outfile_json = bare_module_mass_data_file[:-4] + '_bare_module_mass.json'

    data = _read_xlsx_file(xlsx_file=bare_module_mass_data_file, sheet_name=0)
    bare_module_sn = '20UPG' + ''.join(data[6, 2].replace(' ', '-').split('-'))

    datetime_str = data[6, 6]
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    bare_module_mass = round(data[24, 3], 3) * 1000.0  # in mg

    json_string = {
            "component": bare_module_sn,
            "testType": "MASS_MEASUREMENT",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": True,
            "problems": False,
            "properties": {
                "SCALE_ACCURACY": 1,  # in mg
                "ANALYSIS_VERSION": None},
            "results": {
                "MASS": bare_module_mass}
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json


def convert_bare_module_vi_data(bare_module_vi_data_file):
    outfile_json = bare_module_vi_data_file[:-4] + '_bare_module_VI.json'

    data = _read_xlsx_file(xlsx_file=bare_module_vi_data_file, sheet_name=0)
    bare_module_sn = '20UPG' + ''.join(data[6, 2].replace(' ', '-').split('-'))

    datetime_str = data[6, 6]
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    SENSOR_CONDITION_PASSED_QC = data[63, 5]
    FE_CHIP_CONDITION_PASSED_QC = data[64, 5]

    # Read defect sources
    defect_list = []
    for i in range(13):
        idx = 48 + i
        if data[idx, 5] == 1 or str(data[idx, 5]) == 'yes':
            defect_list.append(i + 1)
    DEFECTS = defect_list

    json_string = {
            "component": bare_module_sn,
            "testType": "VISUAL_INSPECTION",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": True,
            "problems": False,
            "properties": {
                "ANALYSIS_VERSION": None},
            "results":{
                "DEFECTS": DEFECTS,
                "SMD_COMPONENTS_PASSED_QC": None,
                "SENSOR_CONDITION_PASSED_QC": SENSOR_CONDITION_PASSED_QC,
                "FE_CHIP_CONDITION_PASSED_QC": FE_CHIP_CONDITION_PASSED_QC,
                "GLUE_DISTRIBUTION_PASSED_QC": None,
                "WIREBONDING_PASSED_QC": None,
                "PARYLENE_COATING_PASSED_QC": None
                }
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json

def upload_bare_module_data(bare_module_metrology_data_json=None, bare_module_mass_data_json=None, bare_module_vi_data_json=None, bare_module_vi_pictures=None):
    ''' Upload bare module data
    '''
    with ITkProdDB() as itk_prodDB:
        if bare_module_metrology_data_json is not None:
            data = _read_file(bare_module_metrology_data_json)
            itk_prodDB.upload_bare_module_data(data)
        if bare_module_mass_data_json is not None:
            data = _read_file(bare_module_mass_data_json)
            itk_prodDB.upload_bare_module_data(data)
        if bare_module_vi_data_json is not None:
            itk_prodDB.upload_bare_module_data(data, filename, filename_data)
            for k, filename in enumerate(bare_module_vi_pictures):
                if k == 0:
                    side = "frontside"
                if k == 1:
                    side = "frontside"
                elif:
                    raise RuntimeError('To many VI pictures specified!')
                data = _read_file(bare_module_vi_data_json)
                filename_data = {"testRun": None, # will be set later when test run ID is know
                        "title": "{0} {1}".format(data['component'], side),
                        "description": "{0} {1}".format(data['component'], side),
                        "url": Path(filename),
                        "type": "file"}

if __name__ == "__main__":
    bare_module_data_files = ['/home/yannick/Downloads/ITK bare Modul 140 Metrology Inspect 18.01.2024.xls',
                            ]

    # convert and upload data
    for bare_module_data_file in bare_module_data_files:
        # extract metrology, mass and VI
        bare_module_metrology_data_json = convert_bare_module_metrology_data(bare_module_data_file)
        bare_module_mass_data_json = convert_bare_module_mass_data(bare_module_data_file)
        bare_module_vi_data_json = convert_bare_module_vi_data(bare_module_data_file)
        bare_module_vi_pictures = ["/home/yannick/Downloads/0140 front.JPG", "/home/yannick/Downloads/0140 back.JPG"]  # frontside, backside
        # upload
        upload_bare_module_data(bare_module_metrology_data_json=bare_module_metrology_data_json,
                                bare_module_mass_data_json=bare_module_mass_data_json, 
                                bare_module_vi_data_json=bare_module_vi_data_json,
                                bare_module_vi_pictures=bare_module_vi_pictures)
