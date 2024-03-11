import yaml
import os
import logging
from itkprodDB_interface import ITkProdDB

TESTBENCH_TEMPLATE = '~/git/bdaq_module_QC/bdaq53/bdaq53/testbench_template.yaml'
OUTPUT_FILE_PATH = '~/git/bdaq_module_QC/bdaq53/bdaq53'

module_testbench = {
    'module_type': "common_quad", # Module_type defined in modules/module_types.yaml (e.g. dual, common_quad, SPQ). Leave empty for bare chip.
    'powersupply': {
      'lv_name': 'PowerSupply',  # Name of the LV powersupply unit. Has to be identical to hw_drivers name in periphery.yaml
      'lv_channel': 1,
      'lv_voltage': 3.5, # Default None, set value if LV shall be powered through the interlock environment
      'lv_current_limit': 5.88, # LV Current at wich the module will be initialized
      'hv_name': 'Sourcemeter1', # Name of HV powersupply unit used to provide bias voltage. Has to be identical to hw_drivers name in periphery.yaml
      'hv_voltage': -100, # Default None, set value if HV shall be powered through the interlock environment
      'hv_current_limit': 100e-6 # Default 1e-5, set different value neeeded
    },
    'power_cycle': False # power cycle all chip of this module before scan start}
    }
chip_testbench = {
    'chip_type': "itkpixv1",
    'chip_config_file': '', # If defined: use config from in file (either .cfg.yaml or .h5). If not defined use chip config of latest scan and std. config if no previous scan exists
    'record_chip_status': True, # Add chip statuses to the output files after the scan (link errors and powering infos)
}

chip_testbench_dict = [
{'chip_id': 12, 'receiver': 'rx2', 'send_data': "tcp://127.0.0.1:5502"},
{'chip_id': 13, 'receiver': 'rx3', 'send_data': "tcp://127.0.0.1:5503"},
{'chip_id': 14, 'receiver': 'rx1', 'send_data': "tcp://127.0.0.1:5501"},
{'chip_id': 15, 'receiver': 'rx0', 'send_data': "tcp://127.0.0.1:5500"}
]

def generate_testbench(module_name, ATLAS_SN, module_slot=1, outdir=None, outdir_subfolder=True, outdir_suffix='_QC', powersupply={}):
    logging.info(f'Opening testbench at: {TESTBENCH_TEMPLATE}')
    with open(os.path.expanduser(TESTBENCH_TEMPLATE)) as f:
        testbench = yaml.full_load(f)

    if not outdir:
        outdir = testbench['general']['output_directory']
    if outdir_subfolder:
        if not outdir in [None, '', 'None']:
            testbench['general']['output_directory'] = os.path.join(outdir, module_name + outdir_suffix)

    with ITkProdDB() as itk_prodDB:
        # Example 1: Get Iref trim bits for different modules from PDB
        module_id, chips = itk_prodDB.get_chip_sns_of_module(ATLAS_SN)
    if not testbench['modules']:
        testbench['modules'] = {}
    testbench['modules'][module_name] = module_testbench
    testbench['modules'][module_name]['powersupply'].update(powersupply)
    testbench['modules'][module_name]['identifier'] = module_id
    
    for i, chip_sn in enumerate(chips):
        chip_name = 'chip_' + str(i+1)
        testbench['modules'][module_name][chip_name] = chip_testbench.copy()
        testbench['modules'][module_name][chip_name].update(chip_testbench_dict[i])
        testbench['modules'][module_name][chip_name]['chip_sn'] = chip_sn

    slot = 'module_' + str(module_slot)
    if not testbench['hardware']['qms_dict']:
        testbench['hardware']['qms_dict'] = {}
    testbench['hardware']['qms_dict'].update({slot: module_name})

    outfile = os.path.join(os.path.expanduser(OUTPUT_FILE_PATH), 'testbench_' + module_name.lower() + '.yaml')
    with open(outfile, 'w') as f:
        yaml.dump(testbench, f, default_flow_style=False)


if __name__ == "__main__":
    modules = {'Preprod_16': '20UPGM22110168'}
    for k, v in modules.items():
        generate_testbench(k, v, powersupply={'lv_channel': 2})
