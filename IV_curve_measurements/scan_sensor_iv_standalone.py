import numpy as np
import tables as tb
import logging
from tqdm import tqdm
import matplotlib.pyplot as plt
import time

from basil.dut import Dut


dut = Dut('/home/yannick/git/bdaq53_py3/bdaq53/bdaq53/periphery.yaml')
dut.init()


sensor_T = dut['Thermohygrometer2']



logging.info('Initialized sourcemeter: %s' % dut['SensorBias'].get_name())

voltages = list(range(-0, -201, -5))# + list(range(-44, -261, -4)) + list(range(-262, -401, -2))# + list(range(-110, -351, -10)) + list(range(-352, -501, -2))# voltage steps of the IV curve
max_leakage = 99e-6  # scan aborts if current is higher
max_voltage = -210 # for safty, scan aborts if voltage is higher
current_limit = 100e-6  # HV current limit
wait_settle = 4 # every 5 sec
wait_meas = 0.5  # minimum delay between current measurements in seconds
n_meas = 10
bias_voltage = -5  # if defined ramp bias to bias voltage after scan is finished, has to be less than last scanned voltage
chip_id = ""
sensor_id = '41438-14-03_batch_2'
others = 'IZM_HPK_PAD_11'
output_folder = '/home/yannick/git/bdaq53_py3/bdaq53/bdaq53/scans/output_data/'
output_filename = output_folder + "IV_curve_%s_ID_%s_%s" % (chip_id, sensor_id, others)

logging.info('Measure IV for V = %s' % voltages)
description = np.dtype([('voltage', np.float), ('current', np.float), ('current_err', np.float), ('n_meas', np.int), ('timestamp', np.float), ('rel_humidity', np.float), ('chuck_temp', np.float)])


with tb.open_file(output_filename + '.h5', mode='w') as h5_file:
    #dut['SensorBias'].set_current_limit(0.000001)
    #dut['SensorBias'].set_current_sense_range(0.000001)
    #dut['SensorBias'].set_current_nlpc(10)

    dut['SensorBias'].set_current_limit(current_limit)

    data = h5_file.create_table(h5_file.root, name='IV_data', description=description, title='Data from the IV scan')

    dut['SensorBias'].set_voltage(0)
    dut['SensorBias'].on()

    # for index, voltage in enumerate(voltages):
    for voltage in tqdm(voltages, unit='Voltage step'):
        if voltage > 0:
            RuntimeError('Voltage has to be negative! Abort to protect device.')
        if abs(voltage) <= abs(max_voltage):
            logging.info('Setting voltage to %i V', voltage)
            dut['SensorBias'].set_voltage(voltage)
            actual_voltage = voltage
            time.sleep(wait_settle)
        else:
            logging.info('Maximum voltage with %f V reached, abort', voltage)
            break

        # Measure current
        currents = []
        try:
            current = float(dut['SensorBias'].get_current().split(',')[1])
        except:
            logging.warning('Could not measure current, skipping this voltage step!')
            continue
        if abs(current) > abs(max_leakage):
            logging.info('Maximum current with %e I reached, abort', current)
            data.row['voltage'] = voltage
            data.row['current'] = current
            data.row['current_err'] = 0.0
            data.row['n_meas'] = 1
            data.row['timestamp'] = time.time()
            data.row['rel_humidity'] = float(dut['Thermohygrometer2'].get_humidity())
            data.row['chuck_temp'] = float(dut['Thermohygrometer2'].get_temperature())
            break
        # Take mean over several measuerements
        for _ in range(n_meas):
            current = float(dut['SensorBias'].get_current().split(',')[1])
            logging.info('V = %f, I = %e', voltage, current)
            currents.append(current)
            time.sleep(wait_meas)
        # Store data
        sel = np.logical_and(np.array(currents) / np.mean(np.array(currents)) < 2.0, np.array(currents) / np.mean(np.array(currents)) > 0.5)
        data.row['voltage'] = voltage
        data.row['current'] = np.mean(np.array(currents)[sel])
        data.row['current_err'] = np.std(currents)
        data.row['n_meas'] = n_meas
        data.row['timestamp'] = time.time()
        data.row['rel_humidity'] = float(dut['Thermohygrometer2'].get_humidity())
        data.row['chuck_temp'] = float(dut['Thermohygrometer2'].get_temperature())

        print(np.mean(np.array(currents)[sel]), time.time(),  float(dut['Thermohygrometer2'].get_humidity()),  float(dut['Thermohygrometer2'].get_temperature()))
        data.row.append()
        data.flush()

    if bias_voltage and bias_voltage <= 0:
        logging.info('Ramping bias voltage down from %f V to %f V', actual_voltage, bias_voltage)
        # Ramp bias down
        for voltage in tqdm(range(actual_voltage, bias_voltage + 1, 5)):
            time.sleep(1)
            dut['SensorBias'].set_voltage(voltage)
        dut['SensorBias'].off()

logging.info('Analyze and plot results')
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

