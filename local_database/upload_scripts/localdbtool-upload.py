#!/usr/bin/env python3
#################################
# Author: Arisa Kubota
# Email: arisa.kubota at cern.ch
# Date: July 2019
# Project: Local Database for YARR
#################################

### Common
import os, sys, time, argparse, yaml, json
from getpass          import getpass
from pymongo          import MongoClient, errors, DESCENDING
from bson.objectid    import ObjectId
from datetime         import datetime
import pprint
from pathlib import Path
import traceback

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),'../lib/localdb-tools/modules'))
from localdb import *
import register
from register import RegisterData, ScanData, DcsData, CompData

import module_qc_database_tools
from module_qc_database_tools.chip_config_api import ChipConfigAPI
from module_qc_database_tools.core import Module
from module_qc_database_tools.utils import (
    chip_uid_to_serial_number,
    get_layer_from_serial_number,
)

### global variables
home = os.environ['HOME']
if not 'HOSTNAME' in os.environ:
    hostname = 'default_host'
else:
    hostname = os.environ['HOSTNAME']
global db
global localdb

### functions
import common
from common import JsonParsingError

### log
import db_logging
import logging
global logfile
logger = logging.getLogger('Log')
logfile = '' # default. written in HOME/.yarr/localdb/log/log (Old logs are saved as log-old up to log-old-9)

##############
# Exceptions #
##############

class CommandError(Exception):
    pass

class DataError(ValueError):
    pass

class ValidationError(Exception):
    pass

class RegisterError(Exception):
    pass

class InteractiveExit(Exception):
    pass

#######################
### local functions ###
#######################

def getArgs():
    logger.debug('Get Arguments.')
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        'command',
        help='option*\t\tfuntion\n' +
             'init\t\tInitialize upload function and check connection to Local DB\n'+
             'comp\t<file>\tRegister component data from specified connectivity file\n'+
             'scan\t<dir>\tUpload scan data from specified directory\n'+
             'dcs\t<dir>\tUpload DCS data from specified directory\n'+
             'cache\t\tUpload cache data\n'+
             'check\tcomp\tCheck registered component data\n'+
             '     \tchip\tCheck registered chip data',
        type=str,
        nargs='*'
    )
    parser.add_argument('--config',         help='Set User Config Path of Local DB Server.', type=str)
    parser.add_argument('--username',       help='Set the User Name of Local DB Server.',    type=str)
    parser.add_argument('--password',       help='Set the Password of Local DB Server.',     type=str)
    parser.add_argument('--database', '-d', help='Set Database Config Path',                 type=str)
    parser.add_argument('--user', '-u',     help='Set User Config Path',                     type=str)
    parser.add_argument('--site', '-i',     help='Set Site Config Path',                     type=str)
    parser.add_argument('--conn',           help='Set Connectivity Config Path',             type=str)
    parser.add_argument('--log',            help='Set Log Mode',                             action='store_true')
    parser.add_argument('--interactive',    help='Set Interactive Mode',                     action='store_true')
    parser.add_argument('--QC',             help='Set QC Mode',                              action='store_true')
    parser.add_argument('--tag',            help='Set Scan Tags',                            type=str)
    args = parser.parse_args()

    if args.config:
        conf = common.readCfg(args.config)
        if 'username' in conf and not args.username: args.username = conf['username']
        if 'password' in conf and not args.password: args.password = conf['password']

    return args

def checkUploadData(self):
    """
    This function check if data registered by searching with data id
    """
    logger.info( f'localdbtool-upload.checkUploadData' )
    logger.info('Check if TestRun Data registered.')
    tr_oids = []
    for tr_oid in self.tr_oids:
        try:
            self.checkDb()
            status = self._check_test_run(tr_oid)
            for i, oid in enumerate(status['_id']):
                if status['passed'][i]: tr_oids.append(oid)
        except DBConnectionError:
            pass
        
    logger.info( f'localdbtool-upload.checkUploadData: done' )
    return tr_oids

common.addInstanceMethod(ScanData, checkUploadData)

def checkUploadData(self):
    """
    This function check if data registered by searching with data id
    """
    logger.info( f'localdbtool-upload.checkUploadData' )
    logger.info('Check if DCS data registered.')
    ctr_oids = []
    for entry in self.ctr_oids:
        try:
            self.checkDb()
            oid = self._check_dcs(entry['ctr_oid'], entry['key'], entry['num'], entry['description'])
            ctr_oids.append(oid)
        except DBConnectionError:
            pass
    return ctr_oids

common.addInstanceMethod(DcsData, checkUploadData)

######################
### main functions ###
######################

def checkDb(self, i_log={}, i_path=''):
    """
    This function check connection to Local DB
    """
    logger.debug( f'localdbtool-upload.checkDb' )
    logger.debug('Initialize.')
    args = getArgs()

    if self.dbstatus:
        try:
            self.localdb.list_collection_names()
        except:
            raise DBConnectionError
    else:
        db = LocalDb()
        db_cfg = common.readDbCfg(args, i_log.get('dbCfg', {}), i_path)
        db.setCfg(db_cfg)

        



        if args.username: db.setUsername(args.username)
        if args.password: db.setPassword(args.password)

        db.checkConnection()

        localdb = db.getLocalDb()
        toolsdb = db.getLocalDbTools()
        self.setDb(db_cfg, localdb, toolsdb)
        self.mongodb = db.getClient()

        now = datetime.utcnow()

        
            
        default_tags = ["MHT", "TUN", "PFA", "PFA_NOHV"]

        for t in default_tags:

            if not toolsdb.viewer.tag.categories.find_one( { 'name' : t, 'class' : 'scan' } ):

                toolsdb.viewer.tag.categories.insert_one( { 'name' : t,
                                                            'class' : 'scan',
                                                            'sys': { 'cts': now,
                                                                     'mts': now,
                                                                     'rev': 0 } } )
                
                


common.addInstanceMethod(RegisterData, checkDb)

def checkConfigFormat(self, i_dir='', i_log={}, i_path=''):
    """
    This function checks config files
    """
    logger.debug( f'localdbtool-upload.checkConfigFormat' )
    logger.debug('Check config files before scan')
    args = getArgs()

    # user
    user_json = common.readUserCfg(args, i_log.get('userCfg',{}), i_path)
    self.setUser(user_json)

    # site
    site_json = common.readSiteCfg(args, i_log.get('siteCfg',{}), i_path)
    self.setSite(site_json)

    # connectivity
    conn_jsons = common.readJson(args.conn) if args.conn else i_log.get('connectivity',{})
    
    try:
        conn_dir = Path( args.conn ).parent
    except Exception as e:
        conn_dir = ''
        str(e)
    
    logger.debug( f'checkConfigFormat: conn_dir = {conn_dir}' )
    logger.debug( 'localdbtool-upload: checkConfigFormat(): conn_jsons = ' + pprint.pformat( conn_jsons ) )
    
    self.checkDb()
    
    if not type(conn_jsons)==type([]):
        self.setConnCfg(conn_jsons, i_dir, conn_dir)
    else:
        for conn in conn_jsons:
            self.setConnCfg(conn, i_dir)

common.addInstanceMethod(RegisterData, checkConfigFormat)

def verifyData(self, i_log={}):
    """
    This function verifies config files for QC
    """
    logger.debug( f'localdbtool-upload.verifyData' )
    logger.debug('Verify config files for QC')
    args = getArgs()

    QC = args.QC if args.QC else i_log.get('dbCfg',{}).get('QC',False)
    self.verifyCfg(QC)
    if not args.log and args.interactive:
        logger.warning('-> Confirmation')
        logger.warning('Is this ok to upload data into Local DB?')
        logger.warning('\033[5m(Please answer Y/y to continue or N/n to exit.)\033[0m')
        while True:
            answer = input('[y/n]: ')
            if answer.lower()=='y':
                break
            elif answer.lower()=='n':
                raise InteractiveExit

common.addInstanceMethod(ScanData, verifyData)

def verifyData(self, i_log={}):
    """
    This function verifies config files for DCS uploading
    """
    logger.debug( f'localdbtool-upload.verifyData' )
    logger.debug('Verify config files for DCS uploading')
    args = getArgs()
    self.environments = []

    logger.info('Loading DCS information ...')
    self.verifyCfg(i_log)
    registered_keys=[]
    ctr_oids = []
    for env_json in i_log['environments']:
        env_json = self.verifyDcsData(env_json)
        if env_json['chip'] and env_json['chips']==[] and env_json['registered_chips']==[]:
            logger.error("Your chip/module '{}' may be not registered in Local DB.".format(env_json['chip']))
            logger.error("Please register your chip/module in Local DB before associating DCS data to it.")
            logger.error("No DCS data was uploaded to Local DB.")
            raise DataError("No DCS data was uploaded to Local DB.")

        if not env_json['registered_oids']==[]:
            if not args.log and args.interactive:
                self.confirmDcsData(env_json)
                logger.warning('DCS data with the key "{}" is already registered in Local DB.'.format(env_json['key']))
                logger.warning('Do you continue to upload this data into Local DB? [y/n]')
                logger.warning('\033[5m(Please answer Y/y to append new data or N/n to skip this registration.)\033[0m')
                while True:
                    answer = input('[y/n]: ')
                    if answer.lower()=='y':
                        env_json['ctr_oids'] = env_json['ctr_oids'] + env_json['registered_oids']
                        env_json['chips'] = env_json['chips'] + env_json['registered_chips']
                        env_json['registered_chips'] = []
                        env_json['registered_oids'] = []
                        break
                    elif answer.lower()=='n':
                        registered_keys.append(env_json['key'])
                        break
            else:
                registered_keys.append('"{}"'.format(env_json['key']))
        if not env_json['ctr_oids']==[] or not env_json['registered_oids']==[]:
            self.environments.append(env_json)
            if not env_json['ctr_oids']==[]:
                ctr_oids = ctr_oids + env_json['ctr_oids']
    self.tr_oids = []
    if not ctr_oids==[]:
        for env_json in self.environments:
            self.confirmDcsData(env_json)
    if not registered_keys==[]:
        logger.warning('DCS data with the key {} is already registered in Local DB, so skip.'.format(', '.join(registered_keys)))
    if ctr_oids==[]:
        logger.error('No DCS data needed to be uploaded.')
        raise DataError
    else:
        if not args.log and args.interactive:
            logger.warning('-> Confirmation')
            logger.warning('Is this ok to upload DCS data into Local DB?')
            logger.warning('\033[5m(Please answer Y/y to continue or N/n to exit.)\033[0m')
            while True:
                answer = input('[y/n]: ')
                if answer.lower()=='y':
                    break
                elif answer.lower()=='n':
                    raise InteractiveExit

common.addInstanceMethod(DcsData, verifyData)

def setCache(self, i_dir, i_opt):
    """
    This function sets chache directory where the log file is placed
    a. scan upload: path/to/cache/scanLog.json
    b. DCS upload: path/to/cache/dbDcsLog.json
    """
    i_dir = os.path.realpath(os.path.abspath(i_dir))
    logger.debug('loadbtool-upload.setCache')
    logger.debug('Write cache data: {}.'.format(i_dir))
    args = getArgs()

    ##################################
    # Set cache directory and log file
    #register.__global.dir_path = i_dir
    remove = False
    try:
        if i_opt=='scan':
            self.writeScan(i_dir)
        elif i_opt=='dcs':
            self.writeDcs(i_dir)
        else:
            return
    except DataError as e:
        logger.warning( str(e) )
        remove = True
    except Exception as e:
        logger.warning( str(e) )
        if not args.log and args.interactive:
            logger.warning('Do you want to keep this data in the cache list and retry the upload later?')
            while True:
                answer = input('[y/n]: ')
                if answer.lower()=='y':
                    remove = False
                    break
                elif answer.lower()=='n':
                    remove = True
                    break
    self.listCache(i_dir, i_opt, remove)
    logger.debug('loadbtool-upload.setCache: done')

common.addInstanceMethod(RegisterData, setCache)

def writeScan(self, i_dir):
    """
    This function uploads scan data from result data files following scanLog.json
    """
    logger.debug( f'localdbtool-upload.writeScan' )
    logger.debug('Write cache scan data: {}.'.format(i_dir))
    logger.debug('Cache Directory: {}'.format(i_dir))

    args = getArgs()

    # scanLog.json
    log_path = 'scanLog.json'
    log_json = common.readJson('{0}/{1}'.format(i_dir, log_path))
    if log_json=={}:
        logger.error('Not found {0} in {1}'.format(log_path, i_dir))
        logger.error('Specify the correct path to result directory')
        raise DataError
    log_json['QC'] = args.QC


    # DB Connection
    logger.debug( f'localdbtool-upload.writeScan: calling checkConfigFormat()' )
    self.checkConfigFormat(i_dir, log_json, log_path)
    
    logger.debug( f'localdbtool-upload.writeScan: calling checkDb()' )
    self.checkDb(log_json, log_path)

    # Validation for QC
    logger.debug( f'localdbtool-upload.writeScan: calling verifyData()' )
    self.verifyData(log_json)

    # scanLog.json
    logger.debug( f'localdbtool-upload.writeScan: reading scanLog.json' )
    if 'startTime' in log_json:
        start_timestamp = log_json['startTime']
    elif 'timestamp' in log_json:
        start_timestamp = time.mktime(time.strptime(log_json['timestamp'], '%Y-%m-%d_%H:%M:%S'))
    else:
        start_timestamp = datetime.now().timestamp()
    if 'finishTime' in log_json:
        finish_timestamp = log_json['finishTime']
    else:
        finish_timestamp = start_timestamp
    log_json['startTime']  = start_timestamp
    log_json['finishTime'] = finish_timestamp

    # testType
    logger.debug( f'localdbtool-upload.writeScan: reading testType' )
    if 'testType' in log_json:
        test_type = log_json['testType']
    elif 'exec' in log_json:
        command = log_json['exec']
        for i, com in enumerate(command.split(' ')):
            if com=='-s':
                scan_command = command.split(' ')[i+1]
                break
        test_type = scan_command.split('/')[-1].split('.')[0]
    else:
        test_type = 'unknown_type'
    log_json['testType'] = test_type

    # test data upload
    """
    Almost all information of scanLog.json will be stored as test data with keeping the format.
    (Config data and timestamps are stored in the specific format.)
    """
    
    logger.debug( f'localdbtool-upload.writeScan: creating ChipConfigAPI' )
    chip_api = ChipConfigAPI( self.mongodb )
    
    ## start
    conn_jsons = self.setTestRun(log_json)
                
    ## config and attachment
    for conn_json in conn_jsons:
        ### config for testRun
        for key in log_json:
            if not 'Cfg' in key: continue
            cfg_json = log_json[key]
            self.setConfig(cfg_json, key, key, 'testRun', {}, conn_json)
        scan_cfg_path = '{0}/{1}.json'.format(i_dir, test_type)
        cfg_json = common.readJson(scan_cfg_path)
        
        self.setConfig(cfg_json, test_type, 'scanCfg', 'testRun', {}, conn_json)

        logger.debug( '\t conn_json = ' + pprint.pformat( conn_json ) )
        for chip_json in conn_json['chips']:
            filename = 'chipCfg'
            chip_cfg_name = chip_json['config'].split('/')[len(chip_json['config'].split('/'))-1]

            hexSN = None
            chip_SN = None
            
            # first loop -- chip config storing
            for file_name in os.listdir(i_dir):

                ### config for componentTestRun
                if all( [ phrase in file_name for phrase in [chip_cfg_name, 'after'] ] ):

                    logger.info( f'processing file {file_name}...' )

                    cfg_json = common.readJson('{0}/{1}'.format(i_dir, file_name))
                    print('{0}/{1}'.format(i_dir, file_name))
                    title = '{}Cfg'.format(file_name.split(chip_cfg_name)[1][1:])
                    
                    hexSN   = cfg_json.get('RD53B').get('Parameter').get('Name')
                    chip_SN = chip_json.get('serialNumber')
                    stage   = conn_json.get('stage')

                    branch = 'default'
                    warm_list = ['WARM', 'PARYLENE_UNMASKING', 'WIREBOND_PROTECTION', 'THERMAL_CYCLES', 'LONG_TERM_STABILITY_TEST' ]
                    cold_list = ['COLD']
                    
                    if any( [ phrase in stage for phrase in warm_list ] ):
                        branch = 'warm'
                    elif any( [ phrase in stage for phrase in cold_list ] ):
                        branch = 'cold'
                    
                    try:

                        logger.debug('localdbtool-upload.writeScan: writing config information to componentTestRun...')
                        
                        config_id = chip_api.checkout( chip_SN, stage, branch )

                        logger.info( f'checked-out config: id = {config_id}')

                        commit_message = f'Submitted by YARR-dbAccessor (hostname: {self.user_json.get("HOSTNAME")}, user: {self.user_json.get("USER")})'
                        
                        if config_id == None:
                            before_cfg_json = common.readJson( '{0}/{1}'.format(i_dir, file_name).replace('after','before') )
                            config_id = chip_api.create_config( chip_SN, stage, branch )
                            chip_api.commit( config_id, before_cfg_json, commit_message )

                        prev_revision_id = str( chip_api.get_revision_id( config_id, 'HEAD' ) )
                        this_revision_id = str( chip_api.commit( config_id, cfg_json, commit_message ) )

                        logger.debug( f'prev_revision_id = {prev_revision_id}' )
                        logger.debug( f'this_revision_id = {this_revision_id}' )

                        ctrs = [ ctr for ctr in self.localdb.componentTestRun.find( { 'serialNumber' : chip_SN }, sort=[ ("_id", -1 ) ] ) ]

                        ctr_id = ctrs[0].get("_id")

                        self.localdb.componentTestRun.update_one( { '_id' : ctr_id },
                                                                  { '$set' : { 'config_id' : config_id,
                                                                               'config_revision_prev' : prev_revision_id,
                                                                               'config_revision_current' : this_revision_id } } )
                    except Exception as e:
                        logger.error( str(e) )
                        logger.error( 'failure in recording config info to componentTestRun!' )
                        raise e
                    
                    logger.info( f'done processing file {file_name}.' )
                    break
                

            # second loop -- result files storing
            for file_name in os.listdir(i_dir):
                logger.debug( f'chip_SN = {chip_SN}, file_name = {file_name}, hexSN = {hexSN}' )
                #try:
                if '{}_'.format(hexSN) in file_name:
                    if any( [ ext in file_name for ext in ['png', 'jpg', 'pdf'] ] ):
                        continue
                    
                    file_path = '{0}/{1}'.format(i_dir, file_name)
                    histoname = file_name.split('{}_'.format(hexSN))[1].split('.')[0]
                    logger.info( f'writeScan: attaching {file_path} with histoname {histoname}' )
                    self.setAttachment(file_path, histoname, chip_json, conn_json)
                    continue
                #except Exception as e:
                #    logger.error( str(e) )

    ## finish
    tr_oids = self.completeTestRun(log_json, conn_jsons)

    return True

common.addInstanceMethod(ScanData, writeScan)

def writeDcs(self, i_dir):
    """
    This function uploads DCS data from result data files following dbDcsLog.json
    """
    logger.info('Write cache DCS data: {}.'.format(i_dir))
    logger.info('Cache Directory: {}'.format(i_dir))

    args = getArgs()

    # dcsLog.json
    log_path = 'dbDcsLog.json'.format(i_dir)
    log_json = common.readJson('{0}/{1}'.format(i_dir, log_path))
    if log_json=={}:
        logger.error('Not found {0} in {1}'.format(log_path, i_dir))
        logger.error('Specify the correct path to result directory')
        raise DataError

    # environments
    if not 'environments' in log_json:
        logger.error('No "environments" data in {}'.format(log_path))
        raise DataError

    # timestamp
    if 'startTime' in log_json:
        timestamp = log_json['startTime']
    elif 'timestamp' in log_json:
        timestamp = time.mktime(time.strptime(log_json['timestamp'], '%Y-%m-%d_%H:%M:%S'))
    else:
        timestamp = -1
    log_json['timestamp'] = timestamp

    self.checkConfigFormat(i_dir, log_json, log_path)
    self.checkDb(log_json, log_path)

    logger.info('-> Setting DCS Log {}'.format(log_path))
    self.verifyData(log_json)
    self.setDcs()

    return True

common.addInstanceMethod(DcsData, writeDcs)

def __upload_from_cache(i_opt):
    """
    This function uploads scan/DCS data from cache directories written in HOME/.yarr/localdb/run.dat or HOME/.yarr/localdb/dcs.dat
    """
    logger.info('Upload From Cache List.')
    file_paths = {
        'scan': '{}/.yarr/localdb/run.dat'.format(home),
        'dcs' : '{}/.yarr/localdb/dcs.dat'.format(home)
    }
    file_path = file_paths[i_opt]
    logger.info('Upload {0} cache data from {1}'.format(i_opt, file_path))
    cache_list = []
    if os.path.isfile(file_path):
        with open(file_path,'r') as f:
            cache_list = f.read().splitlines()
    cache_list = list(set(cache_list))
    for cache_dir in cache_list:
        if cache_dir=='': continue
        logger.info('------------------------------')
        if i_opt=='scan': data = ScanData()
        elif i_opt=='dcs': data = DcsData()
        data.setCache(cache_dir, i_opt)
        logger.info('------------------------------')
    cache_list = []
    if os.path.isfile(file_path):
        with open(file_path,'r') as f:
            cache_list = f.read().splitlines()
    if not len(cache_list)==0:
        logger.warning('{} cache data could not be uploade for some reason.'.format(len(cache_list)))
        logger.warning('\tCache list: {}'.format(file_path))
        logger.warning('\tLog file  : {}'.format(logfile))
        logger.warning('Please check error messages in log file and retry the upload,')
        logger.warning('    or delete the data not to upload from the cache list.')

def uploadComp(self, i_path):
    """
    This function registeres component data following connectivity file
    """
    logger.info('loadbtool-upload.uploadComp')
    logger.info('Register Component Data.')
    logger.info('Component Config File: {}'.format(i_path))
    args = getArgs()

    # DB Connection
    self.checkConfigFormat()
    self.checkDb()
    self.verifyCfg()
    self.checkConnCfg(i_path)

    logger.warning('Do you continue to upload data into Local DB? [y/n]')
    logger.warning('\033[5m(Please answer Y/y to continue or N/n to exit.)\033[0m')
    while True:
        answer = input('[y/n]: ')
        if answer.lower()=='y':
            break
        elif answer.lower()=='n':
            raise InteractiveExit
    #self.setComponent()
    logger.info('loadbtool-upload.uploadComp: done')

common.addInstanceMethod(CompData, uploadComp)

def listCache(self, i_dir, i_opt, i_remove=False):
    """
    This function adjusts the cache list written in HOME/.yarr/localdb/run.dat or dcs.dat
    """
    logger.info('loadbtool-upload.listCache')
    file_paths = {
        'scan': '{}/.yarr/localdb/run.dat'.format(home),
        'dcs' : '{}/.yarr/localdb/dcs.dat'.format(home)
    }
    path = file_paths.get(i_opt,'')
    if not path=='':
        if os.path.isfile(path):
            with open(path, 'r') as f:
                cache_dirs = f.read().splitlines()
        else:
            cache_dirs = []
        cache_list = []
        for cache_dir in cache_dirs:
            cache_dir = os.path.realpath(os.path.abspath(cache_dir))
            cache_list.append(cache_dir)
        cache_list = list(set(cache_list))
        if i_remove:
            if i_dir in cache_list: cache_list.remove(i_dir)
        else:
            if not self.checkUploadData()==[]:
                logger.info('Succeeded uploading {0} data from {1}'.format(i_opt, i_dir))
                if i_dir in cache_list:
                    cache_list.remove(i_dir)
        with open(path, 'w') as f:
            if not cache_list==[]:
                logger.warning('{0} data that has not been uploaded is listed in {1}'.format(i_opt.capitalize(), path))
            for line in cache_list:
                if not line or not line=='': f.write('{}\n'.format(line))

common.addInstanceMethod(RegisterData, listCache)

def __set_log(log=False):
    """
    This function sets log configuration
    """
    db_logging.setLogFile(logfile)
    if not log==True:
        db_logging.setLog()
    logger.info('------------------------------')

def __check_command():
    """
    This function checks command notation
    If there is any mistake, this function outputs error message and raises CommandError
    """
    args = getArgs()
    command = args.command
    nargs = len(args.command)-1
    if command==[]:
        logger.error('Usage: localdbtool-upload <command> [--option]')
        logger.error('These are common upload commands used in various situations:')
        logger.error('')
        logger.error('\tinit\t\tInitialize upload function and check connection to Local DB')
        logger.error('\tcomp\t<file>\tRegister component data from specified connectivity file')
        logger.error('\tscan\t<dir>\tUpload scan data from specified directory')
        logger.error('\tdcs\t<dir>\tUpload DCS data from specified directory')
        logger.error('\tcache\t\tUpload cache data')
        logger.error('\tcheck\tcomp\tCheck registered component data')
        logger.error('\t     \tchip\tCheck registered chip data')
        logger.error('')
        logger.error('See \'localdbtool-upload --help\' to check available options')
        logger.error('')
        logger.error('The following argument is required: command')
        raise CommandError
    elif command[0]=='test':
        pass
    elif command[0]=='init':
        pass
    elif command[0]=='comp':
        if nargs==0:
            logger.error('Usage: localdbtool-upload comp <path/to/component/file>')
            logger.error('')
            logger.error('Option \'comp\' requires a parameter.')
            raise CommandError
        if args.log:
            logger.error('Usage: localdbtool-upload comp <path/to/component/file>')
            logger.error('')
            logger.error('Option \'comp\' does not support an option "--log".')
            raise CommandError
    elif command[0]=='scan':
        if nargs==0:
            logger.error('Usage: localdbtool-upload scan <path/to/result/dir>')
            logger.error('')
            logger.error('Option \'scan\' requires a parameter.')
            raise CommandError
    elif command[0]=='dcs':
        if nargs==0:
            logger.error('Usage: localdbtool-upload dcs <path/to/result/dir>')
            logger.error('')
            logger.error('Option \'dcs\' requires a parameter.')
            raise CommandError
    elif command[0]=='cache':
        if nargs==0:
            logger.error('Usage: localdbtool-upload cache scan')
            logger.error('   or: localdbtool-upload cache dcs')
            logger.error('')
            logger.error('Option \'cache\' requires a parameter "scan" or "dcs".')
            raise CommandError
    elif command[0]=='check':
        if args.log:
            logger.error('Usage: localdbtool-upload check')
            logger.error('')
            logger.error('Option \'check\' does not support an option "--log".')
            raise CommandError
    else:
        logger.error('\'{}\' is not upload command. See \'localdbtool-upload --help\' to check available commands and options.'.format(command[0]))
        raise CommandError

def main():
    logger.info('Main Function.')
    global logfile

    args = getArgs()
    command = args.command
    nargs = len(args.command)-1

    try:
        __check_command()
    except CommandError as e:
        logger.warning( str(e) )
        logger.error('')
        logger.error('Command Exception: Aborting...')
        sys.exit(1)

    option = command[0]

    if option=='test':
        sys.exit(0)

    __set_log(args.log) ### logging

    # tags
    tags = []

    if args.tag:

        tag = args.tag.replace("'", "\"")


        if '[' in tag and ']' in tag:

            try:
                tags = json.loads( tag )
                
            except Exception as e:
                logger.warning( 'invalid tags specification' )
                logger.error( str(e) )
                raise e

        else:

            tag = tag.replace("'", "").replace('"', '')
            tags += [ tag ]

    logger.info( 'user tags = ' + pprint.pformat( tags ) )

    #try:
    if option=='init':
        logger.info('Function: Initialize upload function and check connection to Local DB')
        scan = ScanData()
        scan.tags = tags
        try:
            scan.checkDb()
        except Exception as e:
            logger.error( str(e) )
            logger.info('------------------------------')
            sys.exit(1)

    elif option=='comp':
        logger.info('Function: Register component data from specified connectivity file')
        data = CompData()
        try:
            data.uploadComp(command[1])
        except DBConnectionError:
            logger.error('Data upload can be done when the connection to DB is good')
            logger.info('------------------------------')
            sys.exit(2)
        except InteractiveExit:
            logger.info('Exiting...')
            logger.info('------------------------------')
            sys.exit(10)
        except:
            logger.error( str(e) )
            logger.error('Invalid configs for uploading data, aborting...')
            logger.info('------------------------------')
            sys.exit(1)

    elif option=='scan': # verify
        logger.info('Function: Upload scan data from specified directory')
        scan = ScanData()
        scan.tags = tags
        scan.setCache(command[1], option)

    elif option=='dcs': # verify
        logger.info('Function: Upload DCS data from specified directory')
        dcs  = DcsData()
        dcs.setCache(command[1], option)

    elif option=='cache': #verify
        logger.info('Function: Upload cache data')
        __upload_from_cache(command[1])

    elif option=='check': #TODO
        logger.info('Function: Check config files')
        scan = ScanData()
        scan.tags = tags
        try:
            scan.checkConfigFormat()
            scan.checkDb()
            scan.verifyData()
        except DBConnectionError:
            logger.info('------------------------------')
            sys.exit(2)
        except InteractiveExit:
            logger.info('Exiting...')
            logger.info('------------------------------')
            sys.exit(10)
        except Exception as e:
            logger.error( str(e) )
            logger.error('Invalid configs for uploading data, aborting...')
            logger.info('------------------------------')
            sys.exit(1)

    logger.info('------------------------------')
    sys.exit(0)

if __name__ == '__main__': main()
