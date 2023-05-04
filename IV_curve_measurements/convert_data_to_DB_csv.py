''' Script to convert IV curve data from .h5 to .json file in proper format for PDB upload.
'''

import numpy as np
import tables as tb
import csv
import json
import time
import logging
import coloredlogs

from datetime import datetime

# Logger
loglevel = logging.DEBUG  # logging.INFO
fmt = '%(asctime)s - [%(name)-15s] - %(levelname)-7s %(message)s'
log = logging.getLogger('IVFileConverter')
log.setLevel(loglevel)
coloredlogs.install(fmt=fmt, milliseconds=False, loglevel=loglevel)
fh = logging.FileHandler(time.strftime("%Y%m%d_%H%M%S") + '_itkprodDB.log')
fh.setLevel(loglevel)
fh.setFormatter(logging.Formatter(fmt))
log.addHandler(fh)

def convert_h5_to_json(input_file_h5, sensor_sn):
    outfile_json = input_file_h5[:-3] + '.json'
    log.info('Converting {0} to {1}...'.format(input_file_h5, outfile_json))

    with tb.open_file(input_file_h5, 'r') as in_file_h5:
        # Read values from file
        timestamp = in_file_h5.root.IV_data[:]['timestamp']
        voltage = in_file_h5.root.IV_data[:]['voltage']
        current = in_file_h5.root.IV_data[:]['current']
        current_std = in_file_h5.root.IV_data[:]['current_err']
        try:
            rel_humidity = in_file_h5.root.IV_data[:]['rel_humidity']
        except ValueError:
            log.debug('No entry found: rel_humidity')
            rel_humidity = np.zeros_like(current)
        try:
            temperature = in_file_h5.root.IV_data[:]['chuck_temp']
        except ValueError:
            log.debug('No entry found: chuck_temp')
            temperature = np.zeros_like(current)


    # convert to DB format
    start_timestamp = timestamp[0]
    timestamp = (timestamp - start_timestamp).astype(float)  # relative, in sec
    voltage = np.abs(voltage)  # positive voltage values in V
    current = np.abs(current) * 1e6  # positive current in uA
    current_std = current_std * 1e6  # current std in uA
    local_time = datetime.fromtimestamp(start_timestamp)

    # Save to CSV
    insitute = 'BONN'
    date = local_time.strftime("%Y-%m-%dT%H:%MZ")
    prefix = 'A'
    depletion_voltage = '9'
    start_rel_humidity = str(rel_humidity[0])
    start_temp = str(temperature[0])
    legend = 't/s\tU/V\tIavg/uA\tIstd/uA\tT/C\tRH/%'
    header = [[sensor_sn + '  IV'], [insitute + '   ' + date], ["prefex" + prefix], ["depletion_voltage" + depletion_voltage], [start_rel_humidity + '    ' + start_temp], [legend]]

    # # CSV file
    # with open(input_file[:-3] + '.csv', 'w', encoding='UTF8', newline='') as f:
    #     # create the csv writer
    #     writer = csv.writer(f)
    #     # write header
    #     for k in header:
    #         print(k)
    #         writer.writerow(k)
    #     writer = csv.writer(f, delimiter='\t')
    #     for val in zip(timestamp, voltage, current, current_std, temperature, rel_humidity):
    #         writer.writerow(val)
    # ts_list = [0.5, 1.0]


    # JSON file
    json_string = {
        "component": sensor_sn,
        "testType": "IV_MEASURE",
        "institution": insitute,
        "date": date,
        "runNumber": "1",
        "passed": "true", 
        "problems": "false",
        "properties": {
            "HUM": start_rel_humidity,
            "TEMP": start_temp
        },
        "results": {
            "IV_ARRAY": {
                "time": list(timestamp),
                "voltage": list(voltage),
                "current": list(current),
                "sigma current": list(current_std),
                "temperature": list(temperature),
                "humidity": list(rel_humidity)
              },
            "BREAKDOWN_VOLTAGE": 0.0,
            "LEAK_CURRENT": 0.0
        }
    }

    with open(outfile_json, 'w') as outfile:
        json.dump(json_string, outfile,  indent=4)

    return outfile_json


if __name__ == "__main__":
    # Example how to convert .h5 to .json file
    sensor_sn = '20UPIS18100498'
    input_file_h5 = '/home/yannick/Documents/IV_curve_7-1_ID_G12-23_IZM_Sintef3D.h5'
    convert_h5_to_json(input_file_h5, sensor_sn)