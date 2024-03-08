'''
Script to upload module data (.json file) to PDB.
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


def _read_file(filename):
    ''' Read .json file and check if it contains required keys.
    '''
    d = open(filename).read()
    data = json.loads(d)

    return data

def _read_xlsx_file(xlsx_file, sheet_name):
    WS = pd.read_excel(io=xlsx_file, sheet_name=sheet_name, header=None)
    return np.array(WS)

def convert_module_metrology_data(module_metrology_data_file):
    outfile_json = module_metrology_data_file[:-4] + '_module_metrology.json'

    data = _read_xlsx_file(xlsx_file=module_metrology_data_file, sheet_name=1)
    module_sn = data[153, 5] #'20UPG' + ''.join(data[153, 5].replace(' ', '-').split('-'))

    datetime_str = datetime.strptime(data[152, 8], '%d.%m.%Y') # datetime(data[152, 8])
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    average_thickness = list(data[190:194, 4])
    average_thickness_std = [round(float(np.std(average_thickness)), 1)]
    average_thickness_min_max = int(np.max(average_thickness) - np.min(average_thickness))
    connector_thickness = data[200, 4]
    hv_cap_thickness = data[199, 4]
    top_left_alignment = list(data[208:210, 8])
    bottom_right_alignment = list(data[210:212, 8])

    json_string = {
            "component": module_sn,
            "testType": "QUAD_MODULE_METROLOGY",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": True,
            "problems": False,
            "properties": {
                # "OPERATOR": "Wolfgang Dietsche",
                # "INSTRUMENT": "Mitutoyo MF-UH1010TH",
                "ANALYSIS_VERSION": None},
            "results":{
                "AVERAGE_THICKNESS": average_thickness,
                "STD_DEVIATION_THICKNESS": average_thickness_std,
                "THICKNESS_VARIATION_PICKUP_AREA": average_thickness_min_max,
                "THICKNESS_INCLUDING_POWER_CONNECTOR": connector_thickness,
                "HV_CAPACITOR_THICKNESS": hv_cap_thickness,
                "DISTANCE_PCB_BARE_MODULE_TOP_LEFT": top_left_alignment,
                "DISTANCE_PCB_BARE_MODULE_BOTTOM_RIGHT": bottom_right_alignment
                }
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json

def convert_module_mass_data(module_mass_data_file):
    outfile_json = module_mass_data_file[:-4] + '_module_mass.json'

    data = _read_xlsx_file(xlsx_file=module_mass_data_file, sheet_name=1)
    module_sn = data[153, 5] #'20UPG' + ''.join(data[153, 5].replace(' ', '-').split('-'))

    datetime_str = datetime.strptime(data[152, 8], '%d.%m.%Y')
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    module_mass = round(data[188, 4], 3) * 1000.0  # in mg

    json_string = {
            "component": module_sn,
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
                "MASS": module_mass}
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json


def convert_module_vi_assembly_data(module_vi_data_file):
    outfile_json = module_vi_data_file[:-4] + '_bare_module_VI_assembly.json'

    data = _read_xlsx_file(xlsx_file=module_vi_data_file, sheet_name=1)
    module_sn = data[153, 5] #'20UPG' + ''.join(data[153, 5].replace(' ', '-').split('-'))

    datetime_str = datetime.strptime(data[152, 8], '%d.%m.%Y') # datetime(data[152, 8])
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    SENSOR_CONDITION_PASSED_QC = data[235, 5]
    FE_CHIP_CONDITION_PASSED_QC = data[236, 5]
    GLUE_DISTRIBUTION_PASSED_QC = data[237, 5]
    SMD_COMPONENTS_PASSED_QC = data[238, 5]

    # Read defect sources
    defect_list = []
    for i in range(13):
        idx = 220 + i
        if data[idx, 5] == 1 or str(data[idx, 5]) == 'yes':
            defect_list.append(i + 1)
    DEFECTS = defect_list

    json_string = {
            "component": module_sn,
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
                "SMD_COMPONENTS_PASSED_QC": SMD_COMPONENTS_PASSED_QC,
                "SENSOR_CONDITION_PASSED_QC": SENSOR_CONDITION_PASSED_QC,
                "FE_CHIP_CONDITION_PASSED_QC": FE_CHIP_CONDITION_PASSED_QC,
                "GLUE_DISTRIBUTION_PASSED_QC": GLUE_DISTRIBUTION_PASSED_QC,
                "WIREBONDING_PASSED_QC": None,
                "PARYLENE_COATING_PASSED_QC": None
                }
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json

def convert_module_pull_data(module_pull_data_file):
    outfile_json = module_pull_data_file[:-4] + '_module_pull_tests.json'

    data = _read_xlsx_file(xlsx_file=module_pull_data_file, sheet_name=1)
    module_sn = data[153, 5] #'20UPG' + ''.join(data[153, 5].replace(' ', '-').split('-'))

    datetime_str = datetime.strptime(data[152, 8], '%d.%m.%Y')
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    n_pulls = int(data[285, 4])  # 285
    pull_strength_min = float(data[287, 5])
    pull_strength_max = float(data[288, 5])
    pull_strength_mean = float(data[289, 5])
    pull_strength_std = float(data[290, 5])
    less_5G_breaks = int(data[291, 5])
    lift_off = int(data[293, 5]) 
    fe_heel_breaks = round((data[295, 5]) * 100.0 / n_pulls, 1)
    pcb_heel_breaks = round((data[294, 5]) * 100.0 / n_pulls, 1)
    pull_data = list(data[286:306, 8])  # add pull data

    json_string = {
            "component": module_sn,
            "testType": "WIREBOND_PULL_TEST",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": True,
            "problems": False,
            "properties": {
                "OPERATOR": 'Wolfgang Dietsche',
                "INSTRUMENT": 'Bonder F&K Delvotec 56xx',
                "ANALYSIS_VERSION": None},
            "results": {
                "WIRE_PULLS": n_pulls,
                "PULL_STRENGTH": pull_strength_mean,
                "PULL_STRENGTH_ERROR": pull_strength_std,
                "PULL_STRENGTH_MIN": pull_strength_min,
                "PULL_STRENGTH_MAX": pull_strength_max,
                "WIRE_BREAKS_5G": less_5G_breaks,
                "HEEL_BREAKS_ON_FE_CHIP": fe_heel_breaks,
                "HEEL_BREAKS_ON_PCB": pcb_heel_breaks,
                "BOND_PEEL": lift_off,
                "PULL_STRENGTH_GRADING": pull_data}
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json

def convert_module_vi_wirebonding_data(module_vi_data_file):
    outfile_json = module_vi_data_file[:-4] + '_bare_module_VI_wirebonding.json'

    data = _read_xlsx_file(xlsx_file=module_vi_data_file, sheet_name=1)
    module_sn = data[153, 5] #'20UPG' + ''.join(data[153, 5].replace(' ', '-').split('-'))

    datetime_str = datetime.strptime(data[152, 8], '%d.%m.%Y')
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    SENSOR_CONDITION_PASSED_QC = data[319, 5]
    FE_CHIP_CONDITION_PASSED_QC = data[320, 5]
    GLUE_DISTRIBUTION_PASSED_QC = data[321, 5]
    SMD_COMPONENTS_PASSED_QC = data[322, 5]
    WIREBONDING_PASSED_QC = data[323, 5]

    # Read defect sources
    defect_list = []
    for i in range(13):
        idx = 304 + i
        if data[idx, 5] == 1 or str(data[idx, 5]) == 'yes':
            defect_list.append(i + 1)
    DEFECTS = defect_list

    json_string = {
            "component": module_sn,
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
                "SMD_COMPONENTS_PASSED_QC": SMD_COMPONENTS_PASSED_QC,
                "SENSOR_CONDITION_PASSED_QC": SENSOR_CONDITION_PASSED_QC,
                "FE_CHIP_CONDITION_PASSED_QC": FE_CHIP_CONDITION_PASSED_QC,
                "GLUE_DISTRIBUTION_PASSED_QC": GLUE_DISTRIBUTION_PASSED_QC,
                "WIREBONDING_PASSED_QC": WIREBONDING_PASSED_QC,
                "PARYLENE_COATING_PASSED_QC": None
                }
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json


def convert_module_wirebonding_information_data(module_data_file):
    outfile_json = module_data_file[:-4] + '_module_wirebonding_info.json'

    data = _read_xlsx_file(xlsx_file=module_data_file, sheet_name=0)
    module_sn = '20UPGM' + ''.join(str(data[5, 6]).replace(' ', '-').split('-'))
    datetime_str = datetime.strptime(data[4, 8], '%d.%m.%Y')
    date = datetime_str.strftime("%Y-%m-%dT%H:%MZ")

    HUMIDITY = data[8, 8]
    TEMPERATURE = data[8, 7]
    json_string = {
            "component": module_sn,
            "testType": "WIREBONDING",
            "institution": "BONN",
            "runNumber": "1",  # FIXME
            "date": date,
            "passed": True,
            "problems": False,
            "properties": {
                "ANALYSIS_VERSION": None,
                "MACHINE": "Bonder F&K Delvotec 5600",
                "OPERATOR": "Wolfgang Dietsche",
                "BOND_WIRE_BATCH": "1",
                "BOND_PROGRAM": "standard",
                "BONDING_JIG": "standard"
                },
            "results":{
                "HUMIDITY": HUMIDITY,
                "TEMPERATURE": TEMPERATURE
                }
            }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json

def upload_module_data(module_metrology_data_json=None, module_mass_data_json=None, module_vi_assembly_data_json=None, module_pull_data_json=None, module_vi_wirebonding_data_json=None, module_wirebonding_information_data_json=None, module_picture_after_assembly=None, module_picture_after_wirebonding=None):
    ''' Upload module data
    '''
    with ITkProdDB() as itk_prodDB:
        if module_metrology_data_json is not None:
            data = _read_file(module_metrology_data_json)
            itk_prodDB.upload_module_data(data)
        if module_mass_data_json is not None:
            data = _read_file(module_mass_data_json)
            itk_prodDB.upload_module_data(data)
        if module_vi_assembly_data_json is not None:
            filename = module_picture_after_assembly
            data = _read_file(module_vi_assembly_data_json)
            filename_data = {"testRun": None, # will be set later when test run ID is know
                    "title": "{0} after assembly".format(data['component']),
                    "description": "{0} after assembly".format(data['component']),
                    "url": Path(filename),
                    "type": "file"}
            itk_prodDB.upload_module_data(data, filename, filename_data)
        if module_pull_data_json is not None:
            data = _read_file(module_pull_data_json)
            itk_prodDB.upload_module_data(data)
        if module_vi_wirebonding_data_json is not None:
            filename = module_picture_after_wirebonding
            data = _read_file(module_vi_wirebonding_data_json)
            filename_data = {"testRun": None, # will be set later when test run ID is know
                    "title": "{0} after wirebonding".format(data['component']),
                    "description": "{0} after wirebonding".format(data['component']),
                    "url": Path(filename),
                    "type": "file"}
            itk_prodDB.upload_module_data(data, filename, filename_data)
        if module_wirebonding_information_data_json is not None:
            data = _read_file(module_wirebonding_information_data_json)
            itk_prodDB.upload_module_data(data)


if __name__ == "__main__":
    module_data_files = ['/home/yannick/20UPGM22110131_19012024.xlsx',
                        ]

    pull_data_files = ['/home/yannick/Downloads/Pull Werte  F131 0142.txt']

    module_picture_after_assembly = "/home/yannick/Flex 131 M142.JPG"
    module_picture_after_wirebonding = "/home/yannick/Flex 131 M142 gebondet.JPG"

    # convert and upload data
    if len(module_data_files) != len(pull_data_files):
        raise
    for k in range(len(module_data_files)):
        module_data_file = module_data_files[k]
        pull_data_file = pull_data_files[k]
        # extract metrology, mass, VI and wire bonding quality
        module_metrology_data_json = convert_module_metrology_data(module_data_file)
        module_mass_data_json = convert_module_mass_data(module_data_file)
        module_vi_assembly_data_json = convert_module_vi_assembly_data(module_data_file)
        module_pull_data_json = convert_module_pull_data(pull_data_file, module_vi_assembly_data_json)
        module_vi_wirebonding_data_json = convert_module_vi_wirebonding_data(module_data_file)
        module_wirebonding_information_data_json = convert_module_wirebonding_information_data(module_data_file)
        # upload
        upload_module_data(module_metrology_data_json=module_metrology_data_json,
                           module_mass_data_json=module_mass_data_json,
                           module_vi_assembly_data_json=module_vi_assembly_data_json,
                           module_pull_data_json=module_pull_data_json,
                           module_vi_wirebonding_data_json=module_vi_wirebonding_data_json,
                           module_wirebonding_information_data_json=None, #module_wirebonding_information_data_json,
                           module_picture_after_assembly=module_picture_after_assembly,
                           module_picture_after_wirebonding=module_picture_after_wirebonding
                           )