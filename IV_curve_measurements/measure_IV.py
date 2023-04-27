''' Script for measuring IV curve. Required HW: Keithley 2410 (SMU) + Sensirion Bridge (Temperature Sensor)
'''
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

# Settings
voltages = list(range(-0, -151, -5)) # voltage steps of the IV curve
max_leakage = 99e-6  # scan aborts if current is higher than this value
max_voltage = -155 # for safty, scan aborts if voltage is higher
current_limit = 100e-6  # HV current limit
wait_settle = 4 # time in seconds between two voltage steps (voltage settling)
wait_meas = 0.5  # time in seconds between current measurements
n_meas = 10  # number of measurements per steps (current are averaged)
bias_voltage = -5  # if defined, ramp bias to bias voltage after scan is finished, has to be less than last scanned voltage

chip_id = "A-2-N4KX65-07B0"
sensor_id = 'W15-A'
others = 'IZM_FBK3D_PAD_11'
output_folder = '/home/yannick/git/bdaq53_py3/bdaq53/bdaq53/scans/output_data/'
output_filename = output_folder + "IV_curve_%s_ID_%s_%s" % (chip_id, sensor_id, others)
description = np.dtype([('voltage', np.float), ('current', np.float), ('current_err', np.float), ('n_meas', np.int), ('timestamp', np.float), ('rel_humidity', np.float), ('chuck_temp', np.float)])

# Init devices
dut = Dut('./periphery.yaml')
dut.init()

log.debug('Initialized sourcemeter: %s' % dut['SensorBias'].get_name())
log.debug('Initialized temperature sensor: %s' % dut['Thermohygrometer'].get_name())

log.info('Measure IV for V = %s' % voltages)

with tb.open_file(output_filename + '.h5', mode='w') as h5_file:
    data = h5_file.create_table(h5_file.root, name='IV_data', description=description, title='Data from the IV scan')
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
            data.row['n_meas'] = 1
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
        data.row['n_meas'] = n_meas
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
# output_file_json = convert_h5_to_json(input_file_h5=output_filename + '.h5')

# upload IV data
# upload_iv_data(module_sn='asa', iv_data_file=output_file_json)
