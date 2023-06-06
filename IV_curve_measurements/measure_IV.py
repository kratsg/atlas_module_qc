''' Script for measuring IV curve. Required HW: Keithley 2410 (SMU) + Sensirion Bridge (Temperature Sensor)
'''

# TODO: pass/fail criteria based on max leakage current + breakdown voltage
# TODO: calculate Vdep and Vbreak (20 percent increase in dV = 5 V)...

import numpy as np
import tables as tb
import logging
import coloredlogs
from tqdm import tqdm
import matplotlib.pyplot as plt
import time

from basil.dut import Dut

from upload_IV_curve_data import upload_iv_data
from convert_data_to_DB_csv import convert_h5_to_json

# Compression for data files
FILTER_RAW_DATA = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
FILTER_TABLES = tb.Filters(complib='zlib', complevel=5, fletcher32=False)

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

# data format
description_data = np.dtype([('voltage', float),
                             ('current', float),
                             ('current_err', float),
                             ('timestamp', float),
                             ('rel_humidity', float),
                             ('chuck_temp', float)])

description_meta_data = np.dtype([('sensor_sn', 'U32'),
                                  ('chip_sn', 'U32'),
                                  ('sensor_id', 'U32'),
                                  ('sensor_type', 'U32'),
                                  # ('voltages', 'O'),
                                  ('max_leakage', float),
                                  ('max_voltage', float),
                                  ('current_limit', float),
                                  ('wait_settle', int),
                                  ('wait_meas', float),
                                  ('n_meas', int)])

# Settings
voltages = list(range(-0, -151, -5)) # voltage steps of the IV curve
max_leakage = 99e-6  # scan aborts if current is higher than this value
max_voltage = -155 # for safty, scan aborts if voltage is higher
current_limit = 100e-6  # HV current limit
wait_settle = 4 # time in seconds between two voltage steps (voltage settling)
wait_meas = 0.5  # time in seconds between current measurements
n_meas = 10  # number of measurements per steps (current are averaged)
bias_voltage = -5  # if defined, ramp bias to bias voltage after scan is finished, has to be less than last scanned voltage

# Output
output_folder = '/home/yannick/git/bdaq53_py3/bdaq53/bdaq53/scans/output_data/'
output_filename = output_folder + "IV_curve_%s" % sensor_sn

# Sensor description
sensor_sn = '20UPIS18100498_TEST'  # Sensor ATLAS S/N
chip_sn = "A-2-N4KX65-07B0"  # Chip S/N
sensor_id = 'W15-A'  # Sensor ID from vendor
sensor_type = 'IZM_FBK3D'  # sensor type

# Init devices
dut = Dut('./periphery.yaml')
dut.init()

log.debug('Initialized sourcemeter: %s' % dut['SensorBias'].get_name())
# log.debug('Initialized temperature sensor: %s' % dut['Thermohygrometer'].get_name())
log.info('Measure IV for V = %s' % voltages)
log.info('Storing data in: %s' % output_filename)

with tb.open_file(output_filename + '.h5', mode='w') as h5_file:
    # meta data
    meta_data_table = h5_file.create_table(h5_file.root, name='meta_data', description=description_meta_data,
                                           title='meta_data', filters=FILTER_TABLES)
    meta_data_table.row['sensor_sn'] = sensor_sn
    meta_data_table.row['chip_sn'] = chip_sn
    meta_data_table.row['sensor_id'] = sensor_id
    meta_data_table.row['sensor_type'] = sensor_type
    # meta_data_table.row['voltages'] = voltages
    meta_data_table.row['max_leakage'] = max_leakage
    meta_data_table.row['max_voltage'] = max_voltage
    meta_data_table.row['current_limit'] = current_limit
    meta_data_table.row['wait_settle'] = wait_settle
    meta_data_table.row['wait_meas'] = wait_meas
    meta_data_table.row['n_meas'] = n_meas
    meta_data_table.row.append()
    meta_data_table.flush()
    data = h5_file.create_table(h5_file.root, name='IV_data', description=description_data,
                                title='Data from the IV scan', filters=FILTER_RAW_DATA)

    # dut['SensorBias'].set_current_limit(0.000001)
    # dut['SensorBias'].set_current_sense_range(0.000001)
    # dut['SensorBias'].set_current_nlpc(10)
    dut['SensorBias'].set_current_limit(current_limit)
    dut['SensorBias'].set_voltage(0)
    dut['SensorBias'].on()

    # Voltage scan
    for voltage in tqdm(voltages, unit='Voltage step'):
        if voltage > 0:
            RuntimeError('Voltage has to be negative! Abort to protect device.')
        if abs(voltage) <= abs(max_voltage):
            log.info('Setting voltage to %i V', voltage)
            dut['SensorBias'].set_voltage(voltage)
            actual_voltage = voltage
            time.sleep(wait_settle)
        else:
            log.info('Maximum voltage with %f V reached, abort', voltage)
            break

        # Measure current, humidty and temperature
        rel_humidity = float(dut['Thermohygrometer'].get_humidity())  # measure humidity
        chuck_temperature = float(dut['Thermohygrometer'].get_temperature())  # measure chuck temperature
        currents = []
        try:
            current = float(dut['SensorBias'].get_current().split(',')[1])
        except:
            log.warning('Could not measure current, skipping this voltage step!')
            continue
        if abs(current) > abs(max_leakage):
            log.error('Maximum current with %e I reached, abort', current)
            data.row['voltage'] = voltage
            data.row['current'] = current
            data.row['current_err'] = 0.0
            data.row['timestamp'] = time.time()
            data.row['rel_humidity'] = rel_humidity
            data.row['chuck_temp'] = chuck_temperature
            data.row.append()
            data.flush()
            break
        # Take mean over several measuerements
        for _ in range(n_meas):
            current = float(dut['SensorBias'].get_current().split(',')[1])
            log.info('V = %f, I = %e, RH = %.2f %%, T = %.2f C', voltage, current, rel_humidity, chuck_temperature)
            currents.append(current)
            time.sleep(wait_meas)

        # Store data
        sel = np.logical_and(np.array(currents) / np.mean(np.array(currents)) < 2.0, np.array(currents) / np.mean(np.array(currents)) > 0.5)
        data.row['voltage'] = voltage
        data.row['current'] = np.mean(np.array(currents)[sel])
        data.row['current_err'] = np.std(currents)
        data.row['timestamp'] = time.time()
        data.row['rel_humidity'] = rel_humidity
        data.row['chuck_temp'] = chuck_temperature

        data.row.append()
        data.flush()

    if bias_voltage and bias_voltage <= 0:
        log.info('Ramping bias voltage down from %f V to %f V', actual_voltage, bias_voltage)
        # Ramp bias down
        for voltage in tqdm(range(actual_voltage, bias_voltage + 1, 5)):
            time.sleep(1)
            dut['SensorBias'].set_voltage(voltage)
        dut['SensorBias'].off()

log.info('Analyze and plot results')
with tb.open_file(output_filename + '.h5', 'r+') as in_file_h5:
    data = in_file_h5.root.IV_data[:]
    x, y, yerr = data['voltage'] * (-1), data['current'] * (-1), data['current_err'] * (-1)
    plt.clf()
    plt.errorbar(x, y, yerr, fmt='o', ls='', label='IV Data')
    plt.title('IV curve of %s (Sensor ID %s)' % (chip_id, sensor_id))
    plt.yscale('log')
    plt.ylabel('Current / A')
    plt.xlabel('Voltage / V')
    plt.grid()
    plt.legend()
    plt.savefig(output_filename + '.pdf')

# convert to json
output_file_json = convert_h5_to_json(input_file_h5=output_filename + '.h5', sensor_sn=sensor_sn)

# upload IV data
upload_iv_data(module_sn=module_sn, iv_data_file=output_file_json)