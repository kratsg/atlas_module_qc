import argparse
import os
import sys
import time
import shutil
import datetime
import logging

from time import sleep
from pathlib import Path

import pymongo
import pexpect
import yaml
import hashlib
import click

log = logging.getLogger("LocalDBManager")


bdaq53_localdb_path = Path(__file__).parent.resolve()

# default localdb config
LOCALDB_HOST = "127.0.0.1"
# LOCALDB_URL =
LOCALDB_PORT = 5000  # default localdb port
LOCALDB_ADMIN = "silab"
LOCALDB_ADMIN_PW = "silab"
INSTITUTE = "BONN"
MONGODB_PORT = 27017  # default mongodb port
MONGODB_ADMIN = "mongo_silab"
MONGODB_ADMIN_PW = "silab"
INFLUXDB_PORT = 8086  # default influxdb port
INFLUXDB_ADMIN = "silab"
INFLUXDB_ADMIN_PW = "silab"
GRAFANA_ADMIN = "silab"
GRAFANA_ADMIN_PW = "silab"
DATA_PATH = str((bdaq53_localdb_path / "local_data").resolve())
DB_VERSION = 1.01
MODE = "local"

server_config = None


class DBReset(Exception):
    pass


def getLocalDBUrl():
    if server_config is None:
        log.error("Server configuration not loaded")
        return

    if server_config['LOCALDB_PORT'] != 80:
        return f"http://{server_config['LOCALDB_HOST']}:{server_config['LOCALDB_PORT']}/localdb"
    else:
        return f"http://{server_config['LOCALDB_HOST']}/localdb"


def loadServerConfig():
    log.debug("Loading server configuration")

    global server_config

    if (bdaq53_localdb_path / ".localdb.yaml").exists():
        with open(bdaq53_localdb_path / ".localdb.yaml", "r") as f:
            server_config = yaml.safe_load(f)
    else:
        saveServerConfig()

    if server_config['DATA_PATH'] is not None:
        (Path(server_config['DATA_PATH']) / "mongodb").mkdir(parents=True, exist_ok=True)
        (Path(server_config['DATA_PATH']) / "influxdb").mkdir(parents=True, exist_ok=True)
        (Path(server_config['DATA_PATH']) / "grafana").mkdir(parents=True, exist_ok=True)


def saveServerConfig():
    log.debug("Saving server configuration")

    global server_config

    server_config = {
        "LOCALDB_HOST"     : LOCALDB_HOST,
        "LOCALDB_PORT"     : LOCALDB_PORT,
        "MONGODB_ADMIN"    : MONGODB_ADMIN,
        "MONGODB_ADMIN_PW" : MONGODB_ADMIN_PW,
        "MONGODB_PORT"     : MONGODB_PORT,
        "INFLUXDB_ADMIN"   : INFLUXDB_ADMIN,
        "INFLUXDB_ADMIN_PW": INFLUXDB_ADMIN_PW,
        "INFLUXDB_PORT"    : INFLUXDB_PORT,
        "LOCALDB_ADMIN"    : LOCALDB_ADMIN,
        "LOCALDB_ADMIN_PW" : LOCALDB_ADMIN_PW,
        "GRAFANA_ADMIN"    : GRAFANA_ADMIN,
        "GRAFANA_ADMIN_PW" : GRAFANA_ADMIN_PW,
        "INSTITUTE"        : INSTITUTE,
        "DATA_PATH"        : DATA_PATH,
        "MODE"             : MODE,
    }

    with open(bdaq53_localdb_path / ".localdb.yaml", "w") as f:
        yaml.dump(server_config, f, default_flow_style=False)

def check_environment():
    if server_config["MODE"] == "local":
        return True

    if not shutil.which("docker"):
        log.error("Cannot find docker executable. Is docker installed? See https://gitlab.cern.ch/silab/bdaq53/-/wikis/Local-data-base#installation")
        return False

    child = pexpect.spawn("docker ps")
    if "permission denied" in child.read().decode():
        log.error("Current user has no rights to run docker. See https://gitlab.cern.ch/silab/bdaq53/-/wikis/Local-data-base#faq")
        return False
    return True

def start_database():
    if server_config is None:
        log.error("Server configuration not loaded")
        return

    ENV_TEMPLATE = f"""LOCALDB_USERNAME={server_config['LOCALDB_ADMIN']}
LOCALDB_PASSWORD={server_config['LOCALDB_ADMIN_PW']}

INFLUXDB_USERNAME={server_config['INFLUXDB_ADMIN']}
INFLUXDB_PASSWORD={server_config['INFLUXDB_ADMIN_PW']}

MONGODB_USERNAME={server_config['MONGODB_ADMIN']}
MONGODB_PASSWORD={server_config['MONGODB_ADMIN_PW']}

GRAFANA_USERNAME={server_config['GRAFANA_ADMIN']}
GRAFANA_PASSWORD={server_config['GRAFANA_ADMIN_PW']}
GRAFANA_DOMAIN={server_config['LOCALDB_HOST']}

DATA_PATH_MONGODB={server_config['DATA_PATH']}/mongodb
DATA_PATH_INFLUXDB={server_config['DATA_PATH']}/influxdb
DATA_PATH_GRAFANA={server_config['DATA_PATH']}/grafana"""

    log.info("Creating docker environment file")
    with open(bdaq53_localdb_path / ".env", "w") as f:
        f.write(ENV_TEMPLATE)

    # start comose stack
    log.info("Creating localDB container stack...")
    child = pexpect.spawn("docker compose up -d", encoding="utf-8", logfile=sys.stdout, cwd=str(bdaq53_localdb_path))
    child.expect(pexpect.EOF)
    sleep(7)

    password_hash = hashlib.md5(server_config['LOCALDB_ADMIN_PW'].encode('utf-8')).hexdigest()

    # connect to mongogb usng pymongo
    client = pymongo.MongoClient(host=server_config['LOCALDB_HOST'], port=server_config['MONGODB_PORT'], username=server_config['MONGODB_ADMIN'], password=server_config['MONGODB_ADMIN_PW'], authSource="admin", serverSelectionTimeoutMS=3000)

    log.info("Creating localDB admin user")
    client["localdb"].command("createUser", server_config["LOCALDB_ADMIN"], pwd=server_config["LOCALDB_ADMIN_PW"], roles=[
        {"role": "readWrite", "db": "localdb"},
        {"role": "readWrite", "db": "localdbtools"},
        {"role": "userAdmin", "db": "localdb"},
        {"role": "userAdmin", "db": "localdbtools"}
    ])

    log.info("Creating localDB viewer admin user")
    client["localdbtools"]["viewer.user"].insert_one({
        'sys': {'rev': 0, 'cts': datetime.datetime.now(), 'mts': datetime.datetime.now()},
        'username': server_config['LOCALDB_ADMIN'],
        'name': server_config['LOCALDB_ADMIN'],
        'auth': 'adminViewer',
        'institution': server_config['INSTITUTE'],
        'Email': '',
        'password': password_hash
    })

def init_database():
    if server_config is None:
        log.error("Server configuration not loaded")
        return

    client = pymongo.MongoClient(host=server_config['LOCALDB_HOST'], port=server_config['MONGODB_PORT'], username=server_config['LOCALDB_ADMIN'], password=server_config['LOCALDB_ADMIN_PW'], authSource="localdb", serverSelectionTimeoutMS=3000)

    try:
        localdb = client["localdb"]
    except Exception as e:
        log.error("Cannot connect to localdb - authentication failed")
        return

    if "localdb" not in client.list_database_names():
        log.error(f"Please download the modules from the production database: {getLocalDBUrl()}")
        return False

    collections = localdb.list_collection_names()

    if "fs.files" not in collections:
        localdb["fs.files"].create_index([("hash", pymongo.DESCENDING), ("_id", pymongo.DESCENDING)])
        log.info('Create "fs.files" collection with index')

    if "chip" not in collections or not any(["name" in i for i in list(client.localdb.chip.index_information())]):
        localdb["chip"].create_index([("name", pymongo.DESCENDING)])
        log.info('Create "chip" collection with index')

    if "component" not in collections or not any(["serialNumber" in i for i in list(client.localdb.component.index_information())]):
        localdb["component"].create_index([("serialNumber", pymongo.DESCENDING)])
        log.info('Create "component" collection with index')

    if "testRun" not in collections or not any(["startTime" in i for i in list(client.localdb.testRun.index_information())]):
        localdb["testRun"].create_index([("startTime", pymongo.DESCENDING), ("user_id", pymongo.DESCENDING), ("address", pymongo.DESCENDING)])
        log.info('Create "testRun" collection with index')

    if "componentTestRun" not in collections or not any(["name" in i for i in list(client.localdb.componentTestRun.index_information())]):
        localdb["componentTestRun"].create_index([("name", pymongo.DESCENDING), ("testRun", pymongo.DESCENDING)])
        log.info('Create "componentTestRun" collection with index')

    if "environment" not in collections or not any(["name" in i for i in list(client.localdb.environment.index_information())]):
        localdb["environment"].create_index([("name", pymongo.DESCENDING)])
        log.info('Create "environment" collection with index')


def stop_database():  # Use setup bash script
    child = pexpect.spawn("docker compose down -v", encoding="utf-8", logfile=sys.stdout, cwd=str(bdaq53_localdb_path))
    child.expect(pexpect.EOF)


def _write_index(collection, data):
    def _update_sys(data):
        if "sys" not in data.keys():
            data["sys"] = {"cts": datetime.utcnow(), "mts": datetime.utcnow(), "rev": 0}
        else:
            data["sys"]["mts"] = datetime.utcnow()
            data["sys"]["rev"] += 1
        return data

    data = _update_sys(data)
    if "dbVersion" not in data.keys():
        data["dbVersion"] = DB_VERSION

    if "_id" in data.keys():
        result = collection.replace_one({"_id": data["_id"]}, data)
        if result.modified_count == 1:
            return data["_id"]
        else:
            raise
    else:
        return str(collection.insert_one(data).inserted_id)


def _reset_database(mode):
    """ Drop all non-default information from the database. Recommended only for debugging. """

    log.critical("CAREFUL, this will drop all information from localDB in 3s...")
    log.critical("3...")
    time.sleep(1)
    log.critical("2...")
    time.sleep(1)
    log.critical("1...")
    time.sleep(1)  
    
    client = pymongo.MongoClient(host=server_config['LOCALDB_HOST'], port=server_config['MONGODB_PORT'], username=server_config['LOCALDB_ADMIN'], password=server_config['LOCALDB_ADMIN_PW'], authSource="localdb", serverSelectionTimeoutMS=3000)

    try:
        localdb = client["localdb"]
    except Exception as e:
        log.error("Cannot connect to localdb - authentication failed")
        return

    if mode in ["soft", "data"]:
        client.switch_database("localdb")
        client["fs.files"].drop()
        client["fs.chunks"].drop()
        client["chip"].delete_one({})
        client["config"].delete_one({})
        client["environment"].delete_one({})
        client["componentTestRun"].delete_one({})
        client["testRun"].delete_one({})
        
        client.switch_database("localdbtools")
        client["viewer.query"].delete_one({})
        _write_index(client["viewer.query"], {"runId": "config", "timeStamp": datetime.utcnow()})
    elif mode in ["hard", "all"]:
        client.drop_database("localdb")
        
        client.switch_database("localdbtools")

        client["QC.module.types"].drop()
        client["QC.status"].drop()
        client["viewer.query"].delete_one({})

        _write_index(client["viewer.query"], {"runId": "config", "timeStamp": datetime.utcnow()})

    raise DBReset("LocalDB was reset to default values!")

def reset_database():  # not working
    if server_config is None:
        log.error("Server configuration not loaded")
        return
    
    _reset_database("soft")


def delete_database():
    if not ping_data_base():
        log.error("Database is not running")
    else:
        if server_config is None:
            log.error("Server configuration not loaded")
            return
        try:
            _reset_database("hard")
        except DBReset:
            pass


def ping_data_base():
    if server_config is None:
        log.error("Server configuration not loaded")
        return

    client = pymongo.MongoClient(host=server_config['LOCALDB_HOST'], port=server_config['MONGODB_PORT'], username=server_config['LOCALDB_ADMIN'], password=server_config['LOCALDB_ADMIN_PW'], authSource="localdb", serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")  # The ping command is cheap and does not require auth.
    except pymongo.errors.ConnectionFailure:
        return False

    return True


def check_database_status():
    if server_config is None:
        log.error("Server configuration not loaded")
        return

    if not ping_data_base():
        log.error("No MongoDB reached at %s:%d" % (server_config['LOCALDB_HOST'], server_config['MONGODB_PORT']))
        return False

    client = pymongo.MongoClient(host=server_config['LOCALDB_HOST'], port=server_config['MONGODB_PORT'], username=server_config['LOCALDB_ADMIN'], password=server_config['LOCALDB_ADMIN_PW'], authSource="localdb", serverSelectionTimeoutMS=3000)

    log.info("MongoDB running at %s:%d" % (server_config['LOCALDB_HOST'], server_config['MONGODB_PORT']))

    if "localdbtools" not in client.list_database_names():
        log.error("Cannot find a localdb setup at %s:%d" % (server_config['LOCALDB_HOST'], server_config['MONGODB_PORT']))
        return False
    tools_collections = client["localdbtools"].list_collection_names()

    if "QC.module.types" not in tools_collections:
        log.error(f"Please download the modules types from the production database: {getLocalDBUrl()}/download_pdinfo")
        return False

    if "localdb" not in client.list_database_names():
        log.error(f"Please download the modules from the production database: {getLocalDBUrl()}")
        return False

    collections = client["localdb"].list_collection_names()

    # Do not require downloaded module info from production DB, since interface is likely often not working
    if "QC.module.status" not in collections or "QC.status" not in tools_collections:
        log.warning(f"No modules from ITk production data base were found. Download modules from production database: {getLocalDBUrl()}/download_component")
        # return False

    # Check for collections required for uploading data
    if "component" not in collections or "componentTestRun" not in collections or "fs.files" not in collections or "testRun" not in collections:
        log.error('Not all database collections found. Call "bdaq_localdb --init"')
        return False

    return True


@click.group()
def main():
    pass

@main.command()
def start():
    loadServerConfig()

    # Check if required programs are available
    if not check_environment():
        return

    log.info("Setup local database")
    start_database()
    sleep(0.5)  # some time for start up
    init_database()
    sleep(0.5)  # some time for start up
    if not check_database_status():
        return

    log.info("Done")

@main.command()
def init():
    loadServerConfig()
    log.info("Initialize local database")
    init_database()

@main.command()
def status():
    loadServerConfig()
    log.info("Check local database status")
    if check_database_status():
        log.info("Database ready for usage")

@main.command()
def stop():
    loadServerConfig()
    log.info("Stop local database")
    stop_database()

@main.command()
def delete():
    loadServerConfig()
    log.info("Deleting database")
    delete_database()

@main.command()
def reset():
    loadServerConfig()
    log.info("Resetting database")
    reset_database()

if __name__ == '__main__':
    main()
