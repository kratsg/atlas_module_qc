''' Script for measuring IV curve. Required HW: Keithley 2410 (SMU) + Sensirion Bridge (Temperature Sensor)
'''

import numpy as np
import tables as tb
import logging
import coloredlogs
from tqdm import tqdm
import matplotlib.pyplot as plt
import time
import json
from datetime import datetime
import matplotlib.dates as mdates

from basil.dut import Dut

from upload_IV_curve_data import upload_iv_data
from convert_data_to_DB_csv import convert_h5_to_json
from analyse_iv import analyseIV

# Compression for data files
FILTER_RAW_DATA = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
FILTER_TABLES = tb.Filters(complib='zlib', complevel=5, fletcher32=False)

# Logger
loglevel = logging.DEBUG  # logging.INFO
fmt = '%(asctime)s - [%(name)-15s] - %(levelname)-7s %(message)s'
log = logging.getLogger('IVDataUploader')
log.setLevel(loglevel)
coloredlogs.install(fmt=fmt, milliseconds=False, loglevel=loglevel)

# data format
description_data = np.dtype([('voltage', float),
                             ('current', float),
                             ('current_err', float),
                             ('timestamp', float),
                             ('rel_humidity', float),
                             ('chuck_temp', float)])

description_meta_data = np.dtype([('sensor_sn', 'S32'),
                                  ('sensor_id', 'S32'),
                                  ('sensor_type', 'S32'),
                                  ('max_leakage', float),
                                  ('max_voltage', float),
                                  ('current_limit', float),
                                  ('wait_settle', int),
                                  ('wait_meas', float),
                                  ('n_meas', int)])

# Settings
voltages = list(range(-0, -201, -5)) # voltage steps of the IV curve
max_leakage = 99e-6  # scan aborts if current is higher than this value
max_voltage = -202 # for safty, scan aborts if voltage is higher
current_limit = 100e-6  # HV current limit
wait_settle = 4 # time in seconds between two voltage steps (voltage settling)
wait_meas = 0.5  # time in seconds between current measurements
n_meas = 10  # number of measurements per steps (current are averaged)

# Sensor description
sensor_sn = '20UPGS33300223'  # Sensor ATLAS S/ N
module_sn = '20UPGB42200138'   # Bare module ATLAS S/N
sensor_id = 'V4-1-143813-3-006'  # Sensor ID from vendor
sensor_type = 'IZM_HPK'  # sensor type

# Output
output_folder = '/home/yannick/git/bdaq53_py3/bdaq53/bdaq53/scans/output_data/'
output_filename = output_folder + "IV_curve_%s.h5" % module_sn

# Init devices
dut = Dut('./periphery.yaml')
dut.init()

log.debug('Initialized sourcemeter: %s' % dut['SensorBias'].get_name())
# log.debug('Initialized temperature sensor: %s' % dut['Thermohygrometer'].get_name())
log.info('Measure IV for V = %s' % voltages)
log.info('Storing data in: %s' % output_filename)

with tb.open_file(output_filename, mode='w') as h5_file:
    # meta data
    meta_data_table = h5_file.create_table(h5_file.root, name='meta_data', description=description_meta_data,
                                           title='meta_data', filters=FILTER_TABLES)
    meta_data_table.row['sensor_sn'] = sensor_sn
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

    dut['SensorBias'].set_current_sense_range(100e-6)
    dut['SensorBias'].set_current_nlpc(10)
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

    log.info('Ramping bias voltage down...')
    # Ramp bias down
    for voltage in tqdm(range(actual_voltage, 0, 5)):
        time.sleep(1)
        dut['SensorBias'].set_voltage(voltage)
    dut['SensorBias'].set_voltage(0)
    dut['SensorBias'].off()

log.info('Analyze and plot results')
with tb.open_file(output_filename, 'r+') as in_file_h5:
    data = in_file_h5.root.IV_data[:]
    x, y, yerr = np.abs(data['voltage']), np.abs(data['current']), np.abs(data['current_err'])
    plt.clf()
    plt.errorbar(x, y, yerr, fmt='o', ls='', label='IV Data')
    plt.title('IV curve of %s' % (module_sn))
    plt.yscale('log')
    plt.ylabel('Current / A')
    plt.xlabel('Voltage / V')
    plt.grid()
    plt.legend()
    plt.savefig(output_filename[:-3] + '.pdf')

with tb.open_file(output_filename, 'r+') as in_file_h5:
    data = in_file_h5.root.IV_data[:]
    rel_humidity = data['rel_humidity']
    timestamp = np.array([datetime.fromtimestamp(ts) for ts in data['timestamp']])
    plt.clf()
    plt.plot(timestamp, rel_humidity, ls='-', marker='None', label='Relative humidity')
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m %H:%M:%S'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=1))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
    plt.title('Rel. humidity of %s' % (module_sn))
    plt.ylabel('RH / %')
    plt.xlabel('Time')
    plt.grid()
    plt.ylim(0, 100)
    plt.gcf().autofmt_xdate()
    plt.legend()
    plt.savefig(output_filename[:-3] + '_RH.pdf')

with tb.open_file(output_filename, 'r+') as in_file_h5:
    data = in_file_h5.root.IV_data[:]
    chuck_temp = data['chuck_temp']
    timestamp = np.array([datetime.fromtimestamp(ts) for ts in data['timestamp']])
    plt.clf()
    plt.plot(timestamp, chuck_temp, ls='-', marker='None', label='Chuck temperature')
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%d-%m %H:%M:%S'))
    plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=1))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
    plt.title('Chuck temperature of %s' % (module_sn))
    plt.ylabel('T / °C')
    plt.xlabel('Time')
    plt.grid()
    plt.ylim(0, 30)
    plt.gcf().autofmt_xdate()
    plt.legend()
    plt.savefig(output_filename[:-3] + '_T.pdf')

# analyse
Vbd, Ilc, no_breakdown_flag, v_max, total_flag = analyseIV([output_file_json])
print(Vbd, Ilc, total_flag)

analysed_json = output_file_json[:-5] + "_analysed.json"
# write to file
with open(analysed_json, 'w') as outfile:
    with open(output_file_json, 'r') as infile:
        data_json = json.load(infile)
        data_json["passed"] = total_flag
        data_json["results"]["BREAKDOWN_VOLTAGE"] = Vbd
        data_json["results"]["LEAK_CURRENT"] = Ilc
        data_json["results"]["NO_BREAKDOWN_VOLTAGE_OBSERVED"] = no_breakdown_flag
        data_json["results"]["MAXIMUM_VOLTAGE"] = v_max
        json.dump(data_json, outfile,  indent=4)

# upload IV data
upload_iv_data(module_sn=module_sn, iv_data_file=analysed_json)