import json
import logging
import os
import time
import coloredlogs
import itk_pdb.dbAccess as dbAccess
import sys


class ITkProdDB(object):
    '''
    Main class defininf the ITk Production data base interface.
    '''

    DB_BASE_URL = "https://itkpd-test.unicorncollege.cz/"

    def __init__(self, debug=False):
        '''
            Init ITk production database
        '''
        # self.ITkPDSession = dbAccess.ITkPDSession()
        self.access_code1 = os.getenv('TOKEN1')
        self.access_code2 = os.getenv('TOKEN2')
        self.token = dbAccess.authenticate(accessCode1=self.access_code1, accessCode2=self.access_code2)

        # Logger
        loglevel = logging.DEBUG if debug else logging.DEBUG
        fmt = '%(asctime)s - [%(name)-15s] - %(levelname)-7s %(message)s'
        self.log = logging.getLogger('ITkProdDB')
        self.log.setLevel(loglevel)
        coloredlogs.install(fmt=fmt, milliseconds=False, loglevel=loglevel)
        self.fh = logging.FileHandler(time.strftime("%Y%m%d_%H%M%S") + '_itkprodDB.log')
        self.fh.setLevel(loglevel)
        self.fh.setFormatter(logging.Formatter(fmt))
        self.log.addHandler(self.fh)

        self.log.info('ITk production DB initialised.')

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.log.removeHandler(self.fh)

    def _access_db(self, action, data, method, attachments=None, url=None):
        '''
            Wrapping itkdb.Client.get/post for uniform error handling
        '''

        if url is None:
            baseName = self.DB_BASE_URL
        else:
            baseName = url

        baseName += action

        if attachments is not None:
            # No encoding of data, as this is passed as k,v pairs
            headers = {"Authorization": "Bearer %s" % self.token}
            return dbAccess.doMultiSomething(baseName, paramdata=data,
                                             headers=headers,
                                             method=method, attachments=attachments)

        if data is not None:
            if type(data) is bytes:
                reqData = data
            else:
                reqData = dbAccess.to_bytes(json.dumps(data))
            if url is None:  # Default
                pass  # print("data is: ", reqData)
        else:
            reqData = None

        headers = {'Content-Type': 'application/json'}
        headers.update({"Accept-Encoding": "gzip, deflate"})
        # Header, token
        if self.token is not None:
            headers["Authorization"] = "Bearer %s" % self.token

        result = dbAccess.doRequest(baseName, data=reqData, headers=headers, method=method)
        time.sleep(0.5)

        return result

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


    def get_iref_trims(self, chip_sn=None):
        ''' Returns IREF Trim bit for given chip S/N (ATLAS format)
        '''

        ret = self._access_db(action="getComponent", method="GET", data={"component": chip_sn})
        test_run_id = ret['tests'][0]['testRuns'][0]["id"]
        test_ret = self._access_db(action="getTestRun", method="GET", data={'testRun': test_run_id})

        return self._get_result_value(results=test_ret['results'], test_item='IREF_TRIM')

    def _set_component_stage(self, component_code, component_stage):
        dbAccess.doSomething("setComponentStage", 
                         data ={'component': component_code,
                                'stage'    : component_stage} )

        # use self._access_db(action="setComponent", method="SET", data={"component": sensor_sn})??

    def _get_component_stage(self, component_code):
        ''' Get current stage of component
        '''
        ret = self._access_db(action="getComponent", method="GET", data={"component": component_code})
        current_stage = ret['currentStage']['code']
        return current_stage

    def _get_component_test_runs(self, component_code):
        ret = self._access_db(action="getComponent", method="GET", data={"component": component_code})
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
        dbAccess.doSomething("uploadTestRunResults", iv_data) 

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
        dbAccess.doSomething("uploadTestRunResults", link_to_bare_module_json)


if __name__ == '__main__':
    with ITkProdDB() as itk_prodDB:
        # Example 1: Get Iref trim bits for different chips from PDB
        chip_sns = ['0x17175', '0x17185', '0x17195', '0x171A5']
        for chip_sn in chip_sns:
            chip_sn_atlas = itk_prodDB._convert_chip_sn(chip_sn)
            itk_prodDB.log.info('{0}, {1}, IREF TRIM bit: {2}'.format(chip_sn_atlas, chip_sn, itk_prodDB.get_iref_trims(chip_sn=chip_sn_atlas)))

        # Example 2: Upload IV curve data to PDB
        # module_sn = "20UPGB12200021"
        # iv_data = "/home/yannick/Documents/IV_curve_7-1_ID_G12-23_IZM_Sintef3D.json"
        # itk_prodDB.upload_iv_curve(module_sn=module_sn, iv_data=iv_data)
        