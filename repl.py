#!/usr/bin/python
# -*- coding: UTF-8 -*-
r"""
@author: Martin Klapproth <martin.klapproth@googlemail.com>
"""
import json
import logging
import os
from pprint import pformat

from pymysql import OperationalError

logger = logging.getLogger()
sh = logging.FileHandler("/dev/fd/2")
sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)-12s %(message)s", datefmt='%Y-%m-%d %H:%M:%S'))
logger.addHandler(sh)
logger.setLevel(logging.DEBUG)

import time
import pymysql.cursors

foreign_cursor = None
foreign_connection = None

def stop():
    local_cursor.close()
    local_connection.close()

    if foreign_cursor:
        foreign_cursor.close()
    if foreign_connection:
        foreign_connection.close()

    exit(0)

def get_master_status(cursor):
    cursor.execute('SHOW MASTER STATUS;')
    master_status = cursor.fetchall()
    if not master_status:
        logger.info("Binlog not configured, replication not possible, dying")
        stop()

    return master_status[0]

def get_slave_status(cursor):
    cursor.execute('SHOW SLAVE STATUS;')
    slave_status = cursor.fetchall()
    if not slave_status:
        return None
    return slave_status[0]

LOCAL_PORT = int(os.environ.get("MYSQL_PORT", 3306))
LOCAL_HOST = '127.0.0.1'

FOREIGN_PORT = int(os.environ["MYSQL_JOIN_PORT"])
FOREIGN_HOST = os.environ["MYSQL_JOIN_HOST"]

while True:
    try:
        # Connect to the database
        local_connection = pymysql.connect(
            host=LOCAL_HOST,
            user='root',
            port=LOCAL_PORT,
            password=os.environ["MYSQL_ROOT_PASSWORD"],
            db='mysql',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
    except OperationalError:
        logger.info("Waiting for local DB to come up")
        time.sleep(3)
        continue


    try:
        # Connect to the database
        foreign_connection = pymysql.connect(
            host=FOREIGN_HOST,
            user='root',
            port=FOREIGN_PORT,
            password=os.environ["MYSQL_ROOT_PASSWORD"],
            db='mysql',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
    except OperationalError:
        logger.info("Waiting for foreign DB to come up")
        time.sleep(3)
        continue


    local_cursor = local_connection.cursor()
    foreign_cursor = foreign_connection.cursor()

    foreign_master_status = get_master_status(foreign_cursor)
    logger.info("Foreign master status: %s" % json.dumps(foreign_master_status))

    local_slave_status = get_slave_status(local_cursor)
    if local_slave_status:
        in_sync = True
        logger.error("Replication status: (local: %s:%s, foreign: %s:%s)" % (local_slave_status["Master_Log_File"], local_slave_status["Exec_Master_Log_Pos"], foreign_master_status["File"], foreign_master_status["Position"]))

        if local_slave_status["Slave_IO_Running"] != "Yes":
            logger.error('\033[1;31mSlave IO is not running (%s)\033[1;m' % local_slave_status["Slave_IO_Running"])
            logger.error('\033[1;31m%s\033[1;m' % local_slave_status["Last_IO_Error"])
            in_sync = False
        if not (local_slave_status["Exec_Master_Log_Pos"] == foreign_master_status["Position"]) and (local_slave_status["Master_Log_File"] == foreign_master_status["File"]):
            logger.error("\033[1;31mReplication is out of sync (local: %s:%s, foreign: %s:%s)\033[1;m" % (local_slave_status["Master_Log_File"], local_slave_status["Exec_Master_Log_Pos"], foreign_master_status["File"], foreign_master_status["Position"]))
            in_sync = False
        if not in_sync:
            stop()

        logger.info("\033[1;32mSlave in sync\033[1;m")
    else:
        logger.info("Local slave is not set up, setting up slave now")
        local_cursor.execute('STOP SLAVE;')
        sql = "CHANGE MASTER TO MASTER_HOST='%s', MASTER_PORT=%s, MASTER_USER='root', MASTER_PASSWORD='%s', MASTER_LOG_FILE='%s', MASTER_LOG_POS=%s;" % (
            FOREIGN_HOST, FOREIGN_PORT, os.environ["MYSQL_ROOT_PASSWORD"], foreign_master_status["File"], foreign_master_status["Position"])
        logger.info("Executing Replication SQL: %s" % sql)
        local_cursor.execute(sql)
        local_cursor.execute('START SLAVE;')
        logger.info("\033[1;32mFinished setting up sync %s:%s -> %s:%s\033[1;m" % (FOREIGN_HOST, FOREIGN_PORT, LOCAL_HOST, LOCAL_PORT))

    stop()
