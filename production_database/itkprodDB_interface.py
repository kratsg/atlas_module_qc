import json
import logging
import os
import time
import coloredlogs
import sys
from pathlib import Path

import itkdb


class ITkProdDB(object):
    '''
    Main class defininf the ITk Production data base interface.
    '''

    def __init__(self, debug=False):
        '''
            Init ITk production database
        '''
        # Logger
        loglevel = logging.DEBUG if debug else logging.DEBUG
        fmt = '%(asctime)s - [%(name)-15s] - %(levelname)-7s %(message)s'
        self.log = logging.getLogger('ITkProdDB')
        self.log.setLevel(loglevel)
        coloredlogs.install(fmt=fmt, milliseconds=False, loglevel=loglevel)
        self.fh = logging.FileHandler('ITkProdDB.log')
        self.fh.setLevel(loglevel)
        self.fh.setFormatter(logging.Formatter(fmt))
        self.log.addHandler(self.fh)

        self.client = itkdb.Client(use_eos=True)
        self.client.user._jwt_options["leeway"] = 50 # add more leeway
        self.client.user.authenticate()
        user = self.client.get("getUser", json={"userIdentity": self.client.user.identity})
        self.log.info('ITk production DB initialised. User {0}'.format(user))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.log.removeHandler(self.fh)

    def _convert_chip_sn(self, chip_sn):
        ''' Converts chip S/N (0x....) to ATLAS S/N (20PGFC).
        '''
        return '20UPGFC{0:07d}'.format(int(chip_sn, 16))

    def _get_result_value(self, results, test_item):
        ''' Helper function to search for `test_item` in given dictionary.
        '''
        for d in results:
            for key, val in d.items():
                if test_item == val:
                    return d.get('value', -1)


    def _get_iref_trims_chip(self, chip_sn=None):
        ''' Returns IREF Trim bit for given chip S/N (ATLAS format)
        '''

        ret = self.client.get("getComponent", json={"component": chip_sn})
        test_run_id = ret['tests'][0]['testRuns'][0]["id"]
        test_ret = self.client.get("getTestRun", json={"testRun": test_run_id})

        return self._get_result_value(results=test_ret['results'], test_item='IREF_TRIM')

    def get_irefs_of_module(self, bare_module_sns):
        for bare_module_sn in bare_module_sns:
            self.log.info('Getting Iref trims of bare module: {0}...'.format(bare_module_sn))
            ret = self.client.get("getComponent", json={"component": bare_module_sn})
            for c in ret['children']:
                if c['componentType']['code'] == 'FE_CHIP':
                    chip_sn_atlas = c['component']['serialNumber']
                    chip_sn = hex(int(chip_sn_atlas[-7:]))
                    self.log.info('{0}, {1}, IREF TRIM bit: {2}'.format(chip_sn_atlas, chip_sn, self._get_iref_trims_chip(chip_sn=chip_sn_atlas)))

    def get_module(self, component_sn):
        def get_parent_module(component):
            for p in component['parents']:
                if p['componentType']['code'] == 'MODULE':
                    module_sn = p['component']['serialNumber']
                    self.log.info(f"Parent module found: {p['componentType']['code']} with SN {module_sn}")
                    return module_sn
                elif p['componentType']['code'] in ['BARE_MODULE']:
                    module_sn = p['component']['serialNumber']
                    self.log.info(f"Parent found: {p['componentType']['code']} with SN {module_sn}")
                    bm = self.client.get("getComponent", json={"component": module_sn})
                    return get_parent_module(bm)
            else:
                self.log.warning(f"Found no parent module for {component['componentType']['code']} with SN {component['component']['serialNumber']}")
                return component['component']['serialNumber']

        component = self.client.get("getComponent", json={"component": component_sn})

        if component['componentType']['code'] not in ['MODULE']:
            self.log.warning(f"Component {component['componentType']['code']} with SN {component_sn} is not a module! Searching for parents...")
            return get_parent_module(component)
        else:
            return component_sn

    def get_chip_sns_of_module(self, module_sn):
        module_sn = self.get_module(module_sn)
        module = self.client.get("getComponent", json={"component": module_sn})
        self.log.info(f"Getting FE chips associated to {module['componentType']['code']} with SN {module_sn}...")

        if not module['componentType']['code'] == 'BARE_MODULE':
            for bm in module['children']:
                if bm['componentType']['code'] == 'BARE_MODULE':
                    ret = self.client.get("getComponent", json={"component": bm['component']['serialNumber']})
                    break
            else:
                ret = module
        else:
            ret = module
            for p in module['parents']:
                if p['componentType']['code'] == ['MODULE']:
                    module_sn = p['component']['serialNumber']
                    break
            else:
                self.log.warning(f'Component {module_sn} does not have an assembled module parent! Using bare module...')

        chip_sns = []
        for c in ret['children']:
            if c['componentType']['code'] == 'FE_CHIP':
                chip_sn_atlas = c['component']['serialNumber']
                chip_sn = hex(int(chip_sn_atlas[-7:]))
                chip_sns.append(chip_sn)
        return module_sn, chip_sns


    def check_uploaded_tests(self, module_sn):
        # Check module tests
        ret = self.client.get("getComponent", json={"component": module_sn})
        current_stage = ret['currentStage']['code']
        self.log.info('Checking tests for module: {0} (at stage {1})...'.format(module_sn, current_stage))
        current_stage = ret['currentStage']['code']
        required = _required_tests_module[current_stage]
        # FIXME: VI is special. Needs to be uploaded for MODULE/ASSEMBLY and MODULE/WIREBONDING
        found_tests = []
        for r in ret['tests']:
            if r['code'] in ['VISUAL_INSPECTION']:
                for run in r['testRuns']:
                    test_run = self.client.get("getTestRun", json={"testRun": run['id']})
                    if (test_run['components'][0]['testedAtStage']['code']) == current_stage:
                        self.log.info('Found module test: {0} for module {1}'.format(r['code'], module_sn))
                        found_tests.append(r['code'])
                        break
            else:
                self.log.info('Found module test: {0} for module {1}'.format(r['code'], module_sn))
            found_tests.append(r['code'])

        diff = set(required) - set(found_tests)
        if len(diff) == 0:
            self.log.success('No missing module tests found')
        else:
            self.log.warning('Missing module tests for module {0}: {1}'.format(module_sn, diff))

        # check bare module
        ret = self.client.get("getComponent", json={"component": module_sn})
        # get bare module
        for c in ret['children']:
            if c['componentType']['code'] == 'BARE_MODULE': 
                # bare_module_sn = c['componentType']
                bare_module_sn = c['component']['serialNumber']
                break
        ret = self.client.get("getComponent", json={"component": bare_module_sn})
        current_stage = ret['currentStage']['code']
        required = _required_tests_bare_module[current_stage]
        found_tests = []
        for r in ret['tests']:
            self.log.info('Found bare module test: {0} for bare module {1}'.format(r['code'], bare_module_sn))
            found_tests.append(r['code'])

        diff = set(required) - set(found_tests)

        if len(diff) == 0:
            self.log.success('No missing bare module tests found')
        else:
            self.log.warning('Missing bare module tests for bare module {0}: {1}'.format(bare_module_sn, diff))

    def get_bare_iv_data(self, module_sn, wanted_tests, result):
        # Check module tests
        ret = self.client.get("getComponent", json={"component": module_sn})
        current_stage = ret['currentStage']['code']
        self.log.info('Checking {0} for module: {1} (at stage {2})...'.format(wanted_tests, module_sn, current_stage))

        for c in ret['children']:
            if c['componentType']['code'] == 'BARE_MODULE': 
                # bare_module_sn = c['componentType']
                bare_module_sn = c['component']['serialNumber']
                break
        ret = self.client.get("getComponent", json={"component": bare_module_sn})
        for c in ret['children']:
            if c['componentType']['code'] == 'SENSOR_TILE': 
                # bare_module_sn = c['componentType']
                sensor_sn = c['component']['serialNumber']
                break
        ret = self.client.get("getComponent", json={"component": sensor_sn})


        for r in ret['tests']:
            passed = True
            if r['code'] in wanted_tests:
                for rr in range(len(r['testRuns'])):
                    test_run_id = r['testRuns'][rr]["id"]
                    test_ret = self.client.get("getTestRun", json={"testRun": test_run_id})
                    if test_ret['components'][rr]['testedAtStage']['code'] == 'BAREMODULERECEPTION':
                        break

                for c in criterias['BARE_MODULE_SENSOR_IV']:
                    for res in test_ret['results']:
                        if res['code'] == c:
                            # current_check = ((test_ret['passed']) & (res['value'] > criterias['BARE_MODULE_SENSOR_IV'][c][0]) and (res['value'] < criterias['BARE_MODULE_SENSOR_IV'][c][1]))
                            current_check = (res['value'] > criterias['BARE_MODULE_SENSOR_IV'][c][0]) and (res['value'] < criterias['BARE_MODULE_SENSOR_IV'][c][1])
                            if not current_check:
                                print('{0} out of specs: {1} [{2}] '.format(c, res['value'], criterias['BARE_MODULE_SENSOR_IV'][c]))
                            passed &= current_check
                result['BARE_MODULE_SENSOR_IV'] = passed
                result['module_sn'] = module_sn
    #         else:
    # try:
    #     print('asasas')
    #     result[r['code']] = 2
    #     result['module_sn'] = module_sn
    # except ValueError:  # other tests which are not of interest
    #     pass


        return result

    def get_bare_assembly_data(self, module_sn, wanted_tests, result):
        # Check module tests
        ret = self.client.get("getComponent", json={"component": module_sn})
        current_stage = ret['currentStage']['code']
        self.log.info('Checking {0} for module: {1} (at stage {2})...'.format(wanted_tests, module_sn, current_stage))

        for c in ret['children']:
            if c['componentType']['code'] == 'BARE_MODULE': 
                # bare_module_sn = c['componentType']
                bare_module_sn = c['component']['serialNumber']
                break
        ret = self.client.get("getComponent", json={"component": bare_module_sn})

        for r in ret['tests']:
            if r['code'] in wanted_tests:
                test_run_id = r['testRuns'][0]["id"]
                test_ret = self.client.get("getTestRun", json={"testRun": test_run_id})
                passed = True
                for c in criterias['QUAD_BARE_MODULE_METROLOGY']:
                    for res in test_ret['results']:
                        if res['code'] == c:
                            # if res['code'] == 'DISTANCE_PCB_BARE_MODULE_TOP_LEFT':
                            #     print('ajajaajajaj', res['value'])
                            #     current_check  =  True
                            #     for i in range(2):
                            #         current_check &= (res['value'][i] > criterias['QUAD_MODULE_METROLOGY'][c][i][0]) and (res['value'][i] < criterias['QUAD_MODULE_METROLOGY'][c][i][1])
                            # else:
                            current_check = (res['value'] > criterias['QUAD_BARE_MODULE_METROLOGY'][c][0]) and (res['value'] < criterias['QUAD_BARE_MODULE_METROLOGY'][c][1])
                            if not current_check:
                                print('{0} out of specs: {1} [{2}] '.format(c, res['value'], criterias['QUAD_BARE_MODULE_METROLOGY'][c]))
                            passed &= current_check
                result[r['code']] = passed
                result['module_sn'] = module_sn
        return result

    
    def get_assembly_data(self, module_sn, wanted_tests, result):
        # Check module tests
        ret = self.client.get("getComponent", json={"component": module_sn})
        current_stage = ret['currentStage']['code']
        self.log.info('Checking {0} for module: {1} (at stage {2})...'.format(wanted_tests, module_sn, current_stage))

        for r in ret['tests']:
            passed = True
            if r['code'] in wanted_tests:
                test_run_id = r['testRuns'][0]["id"]
                test_ret = self.client.get("getTestRun", json={"testRun": test_run_id})
                for c in criterias['QUAD_MODULE_METROLOGY']:
                    for res in test_ret['results']:
                        if res['code'] == c:
                            current_check = True
                            if res['code'] == 'DISTANCE_PCB_BARE_MODULE_TOP_LEFT':
                                for i in range(2):
                                    try:
                                        current_check &= (res['value'][i] > criterias['QUAD_MODULE_METROLOGY'][c][i][0]) and (res['value'][i] < criterias['QUAD_MODULE_METROLOGY'][c][i][1])
                                    except Exception:
                                        print('could not calculate pass/fail')
                                        current_check = False
                            else:
                                current_check = (res['value'] > criterias['QUAD_MODULE_METROLOGY'][c][0]) and (res['value'] < criterias['QUAD_MODULE_METROLOGY'][c][1])
                            if not current_check:
                                print('{0} out of specs: {1} [{2}] '.format(c, res['value'], criterias['QUAD_MODULE_METROLOGY'][c]))
                            passed &= current_check
                result[r['code']] = passed
                result['module_sn'] = module_sn
            # else:
            #     result[r['code']] = 2
            #     result['module_sn'] = module_sn

        return result

    def get_iv_data(self, module_sn, wanted_tests, result):
        # Check module tests
        ret = self.client.get("getComponent", json={"component": module_sn})
        current_stage = ret['currentStage']['code']
        self.log.info('Checking {0} for module: {1} (at stage {2})...'.format(wanted_tests, module_sn, current_stage))
        for r in ret['tests']:
            passed = True
            if r['code'] in wanted_tests:
                test_run_id = r['testRuns'][0]["id"]
                test_ret = self.client.get("getTestRun", json={"testRun": test_run_id})
                # print(test_ret['results'], test_ret['passed'])
                for c in criterias['IV_MEASURE']:
                    for res in test_ret['results']:
                        if res['code'] == c:
                            #current_check = ((test_ret['passed']) & (res['value'] > criterias['IV_MEASURE'][c][0]) and (res['value'] < criterias['IV_MEASURE'][c][1]))
                            current_check = (res['value'] > criterias['IV_MEASURE'][c][0]) and (res['value'] < criterias['IV_MEASURE'][c][1])
                            if not current_check:
                                print('{0} out of specs: {1} [{2}] '.format(c, res['value'], criterias['IV_MEASURE'][c]))
                            passed &= current_check
                result[r['code']] = passed
                result['module_sn'] = module_sn
        return result

    def _set_component_stage(self, component_code, component_stage):
        self.client.post("setComponentStage", json={'component': component_code,
                                                   'stage': component_stage})

    def _get_component_stage(self, component_code):
        ''' Get current stage of component
        '''
        ret = self.client.get("getComponent", json={"component": component_code})
        current_stage = ret['currentStage']['code']
        return current_stage

    def _get_component_test_runs(self, component_code):
        ret = self.client.get("getComponent", json={"component": component_code})
        return ret['tests'][0]['testRuns']


    def upload_iv_curve(self, module_sn=None, iv_data=None):
        ''' Upload IV curve data. Uploading IV curve data consists of several steps:
            1) Check if SENSOR TILE is at proper stage (BAREMODULERECEPTION). If not, chnage stage.
            2) Upload IV to SENSOR TILE
            3) Check if BARE MODULE is at proper stage (BAREMODULERECEPTION). If not, chnage stage.
            4) Link IV curve testRun to BARE MODULE
        '''

        sensor_sn = iv_data['component']
        institution = iv_data['institution']

        # Check current stage of SENSOR TILE and change stage if needed.
        current_stage = self._get_component_stage(component_code=sensor_sn) # current stage of sensor tile
        if current_stage == 'BAREMODULERECEPTION': # needs to be at stage: BAREMODULERECEPTION (Bare module reception at ITK institute), otherwise no IV curve data upload possible
            self.log.debug('Current stage of SENSOR TILE ({0}) is ok'.format(current_stage))
        else:
            self.log.debug('Current stage of SENSOR TILE ({0}) is not ok'.format(current_stage))
            if current_stage == "sensor_manufacturer":
                set_stages = ['WAFER_PROCESSING', 'BAREMODULEASSEMBLY', 'BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=sensor_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=sensor_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'WAFER_PROCESSING':
                set_stages = ['BAREMODULEASSEMBLY', 'BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=sensor_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=sensor_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'BAREMODULEASSEMBLY':
                set_stages = ['BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=sensor_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=sensor_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            else:
                self.log.error('Unkown stage ({0})'.format(current_stage))

        # upload IV data to SENSOR TILE
        self.client.post('uploadTestRunResults', json=iv_data)

        # Check current stage of BARE MODULE and change stage if needed.
        current_stage = self._get_component_stage(component_code=module_sn) # current stage of sensor tile
        if current_stage == 'BAREMODULERECEPTION': # needs to be at stage: BAREMODULERECEPTION (Bare module reception at ITK institute), otherwise no IV curve data upload possible
            print('Stage ok:', current_stage)
        else:
            print('stage not okay, current_stage is: %s' %current_stage)
            if current_stage == "sensor_manufacturer":
                set_stages = ['WAFER_PROCESSING', 'BAREMODULEASSEMBLY', 'BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=module_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=module_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'WAFER_PROCESSING':
                set_stages = ['BAREMODULEASSEMBLY', 'BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=module_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=module_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'BAREMODULEASSEMBLY':
                set_stages = ['BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=module_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=module_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            else:
                self.log.error('Unkown stage ({0})'.format(current_stage))

        # Get ID of latest test run and link to bare module
        test_runs = self._get_component_test_runs(sensor_sn)
        test_runs = sorted(test_runs, key=lambda d: d['stateTs'])  # sort test runs by stateTs (upload date)
        test_run = test_runs[-1]  # get latest test run
        test_run_id = test_run['id']

        link_to_bare_module_json = {
            "component": module_sn,
            "testType": "BARE_MODULE_SENSOR_IV",
            "institution": test_run['institution']['code'],
            "date": test_run['stateTs'],
            "runNumber": test_run['runNumber'],
            "passed": test_run['passed'],
            "problems": test_run['problems'],
            "results": {"LINK_TO_SENSOR_IV_TEST": test_run_id}
        }
        self.log.info("Test: would send data:\n")
        self.log.info(json.dumps(link_to_bare_module_json, indent=4))
        self.client.post('uploadTestRunResults', json=link_to_bare_module_json)

    def upload_flex_data(self, flex_data, filename=None, filename_data=None):
        # FIXME: fix run number
        # Check current stage of BARE MODULE and change stage if needed.
        flex_sn = flex_data['component']
        current_stage = self._get_component_stage(component_code=flex_sn) # current stage of sensor tile
        if current_stage == 'PCB_RECEPTION_MODULE_SITE': # needs to be at stage: PCB_RECEPTION_MODULE_SITE
            print('Stage ok:', current_stage)
        else:
            print('stage not okay, current_stage is: %s' %current_stage)
            if current_stage == "QA_PRE_THERMAL_CYCLE":
                set_stages = ['QA_POST_THERMAL_CYCLE', 'PCB_QC', 'PCB_READY_FOR_MODULE', 'PCB_RECEPTION_MODULE_SITE']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=flex_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=flex_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'QA_POST_THERMAL_CYCLE':
                set_stages = ['PCB_QC', 'PCB_READY_FOR_MODULE', 'PCB_RECEPTION_MODULE_SITE']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=flex_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=flex_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'PCB_QC':
                set_stages = ['PCB_READY_FOR_MODULE', 'PCB_RECEPTION_MODULE_SITE']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=flex_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=flex_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'PCB_READY_FOR_MODULE':
                set_stages = ['PCB_RECEPTION_MODULE_SITE']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=flex_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=flex_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            else:
                self.log.error('Unkown stage ({0})'.format(current_stage))

        self.log.info("Test: would send data:\n")
        self.log.info(json.dumps(bare_module_data, indent=4))
        ret = self.client.post('uploadTestRunResults', json=flex_data)

        if filename is not None:
            filename_data['testRun'] = str(ret['testRun']['id'])
            self.upload_attachment_to_eos(filename=filename, data=filename_data)

    def upload_bare_module_data(self, bare_module_data, filename=None, filename_data=None):
        bare_module_sn = bare_module_data['component']
        # Check current stage of BARE MODULE and change stage if needed.
        current_stage = self._get_component_stage(component_code=bare_module_sn) # current stage of sensor tile
        if current_stage == 'BAREMODULERECEPTION': # needs to be at stage: BAREMODULERECEPTION (Bare module reception at ITK institute)
            print('Stage ok:', current_stage)
        else:
            print('stage not okay, current_stage is: %s' %current_stage)
            if current_stage == "sensor_manufacturer":
                set_stages = ['WAFER_PROCESSING', 'BAREMODULEASSEMBLY', 'BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=bare_module_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=bare_module_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'WAFER_PROCESSING':
                set_stages = ['BAREMODULEASSEMBLY', 'BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=bare_module_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=bare_module_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            elif current_stage == 'BAREMODULEASSEMBLY':
                set_stages = ['BAREMODULERECEPTION']
                for stage in set_stages:
                    stage_old = current_stage
                    self._set_component_stage(component_code=bare_module_sn, component_stage=stage)  # change stage
                    time.sleep(2.0)
                    current_stage = self._get_component_stage(component_code=bare_module_sn)
                    self.log.debug('Changed stage of SENSOR TILE from {0} to {1}.'.format(stage_old, current_stage))
            else:
                self.log.error('Unkown stage ({0})'.format(current_stage))

        self.log.info("Test: would send data:\n")
        self.log.info(json.dumps(bare_module_data, indent=4))
        ret = self.client.post('uploadTestRunResults', json=bare_module_data)

        if filename is not None:
            filename_data['testRun'] = str(ret['testRun']['id'])
            self.upload_attachment_to_eos(filename=filename, data=filename_data)


    def upload_module_data(self, module_data, filename=None, filename_data=None):
        module_sn = module_data['component']
        # Check current stage of MODULE and change stage if needed.
        current_stage = self._get_component_stage(component_code=module_sn) # current stage of sensor tile

        if module_data['testType'] == 'WIREBOND_PULL_TEST':
            # FIXME: also change bare module stage
            self._get_component_stage(component_code=module_sn)
            if current_stage != 'MODULE/WIREBONDING':
                print('need to change stage to Wirebonding')
                self._set_component_stage(component_code=module_sn, component_stage='MODULE/WIREBONDING')  # change stage
                time.sleep(2.0)
                new_stage = self._get_component_stage(component_code=module_sn)
                self.log.debug('Changed stage of MODULE from {0} to {1}.'.format(current_stage, new_stage))

        self.log.info("Test: would send data:\n")
        self.log.info(json.dumps(module_data, indent=4))
        ret = self.client.post('uploadTestRunResults', json=module_data)

        if filename is not None:
            filename_data['testRun'] = str(ret['testRun']['id'])
            self.upload_attachment_to_eos(filename=filename, data=filename_data)

    def upload_attachment_to_eos(self, filename=None, data=None):
        with Path(filename).open("rb") as fpointer:
            files = {"data": itkdb.utils.get_file_components({"data": fpointer})}
            response = self.client.post("createTestRunAttachment", data=data, files=files)


if __name__ == '__main__':
    with ITkProdDB() as itk_prodDB:
        # Example 1: Get Iref trim bits for different modules from PDB
        bare_module_sns = ['20UPGB42000111', '20UPGB42000112', '20UPGB42000113', '20UPGB42000114', '20UPGB42000115']
        itk_prodDB.get_irefs_of_module(bare_module_sns)

        # Example 2: Upload IV curve data to PDB
        # module_sn = "20UPGB12200021"
        # iv_data = "/home/yannick/Documents/IV_curve_7-1_ID_G12-23_IZM_Sintef3D.json"
        # itk_prodDB.upload_iv_curve(module_sn=module_sn, iv_data=iv_data)

        # Example 3: Upload data to EOS
        # filename = "/media/yannick/cernbox/ATLAS_Module_Site_Quali_Bonn/Quad_Assembly/data/20UPGM22110018_VI_after_WB.JPG"
        # data = {"testRun": "65561e47b31134004292e90a",
        #         "title": "20UPGM22110018 after WB",
        #         "description": "20UPGM22110018 after WB",
        #         "url": Path(filename),
        #         "type": "file"}
        # itk_prodDB.upload_attachment_to_eos(filename=filename, data=data)
        