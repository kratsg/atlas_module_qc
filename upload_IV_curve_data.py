'''
Script to upload IV curve data (.json file) to PDB.
'''
import json
import time
import logging
import coloredlogs

from itkprodDB_interface import ITkProdDB

# Logger
loglevel = logging.DEBUG  # logging.INFO
fmt = '%(asctime)s - [%(name)-15s] - %(levelname)-7s %(message)s'
log = logging.getLogger('IVDataUploader')
log.setLevel(loglevel)
coloredlogs.install(fmt=fmt, milliseconds=False, loglevel=loglevel)
fh = logging.FileHandler(time.strftime("%Y%m%d_%H%M%S") + '_itkprodDB.log')
fh.setLevel(loglevel)
fh.setFormatter(logging.Formatter(fmt))
log.addHandler(fh)

def _read_file(filename):
    ''' Read .json file and check if it contains required keys.
    '''
    d = open(filename).read()
    data = json.loads(d)

    # Do some validation
    if "component" not in data:
        raise ValueError("Need reference to component, hex string")

    if "testType" not in data:
        raise ValueError("Need to know test type, short code")

    if "institution" not in data or data["institution"] is None:
        raise ValueError("Need to know institution, short code")

    if "runNumber" not in data:
        raise ValueError("Need runNumber field in json file (string)")

    if "passed" not in data:
        raise ValueError("Need passed field (bool) in json file")

    if "results" not in data:
        raise ValueError("Need some test results")

    if "properties" in data:
        for k,v in data["properties"].items():
            if v == "some_string":
                raise ValueError("This looks like a prototype file, property: %s" % k)

    return data

def upload_iv_data(module_sn, iv_data_file):
    ''' Upload IV curve data
    '''
    with ITkProdDB() as itk_prodDB:
        iv_data = _read_file(iv_data_file)
        log.info("Test: would send data")
        log.info(json.dumps(iv_data, indent=4))
        itk_prodDB.upload_iv_curve(module_sn=module_sn, iv_data=iv_data)

if __name__ == "__main__":
    # Example how to upload IV curve data
    module_sn = "20UPGB12200021"
    iv_data_file = "/home/yannick/Documents/IV_curve_7-1_ID_G12-23_IZM_Sintef3D.json"
    upload_iv_data(module_sn, iv_data_file)