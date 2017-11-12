#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# <bitbar.title>MyDaikin</bitbar.title>
# <bitbar.version>v1.0</bitbar.version>
# <bitbar.author>pvdabeel@mac.com</bitbar.author>
# <bitbar.author.github>pvdabeel</bitbar.author.github>
# <bitbar.desc>Display information about and control your Daikin Emura airco units from the Mac OS X menubar</bitbar.desc>
# <bitbar.dependencies>python</bitbar.dependencies>
#
# Licence: GPL v3

# Installation instructions: 
# -------------------------- 
# Ensure you have bitbar installed https://github.com/matryer/bitbar/releases/latest
# Ensure your bitbar plugins directory does not have a space in the path (known bitbar bug)
# Copy this file to your bitbar plugins folder and chmod +x the file from your terminal in that folder
# Run bitbar


try:   # Python 3 dependencies
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen, build_opener
    from urllib.request import ProxyHandler, HTTPBasicAuthHandler, HTTPHandler, HTTPError, URLError
except: # Python 2 dependencies
    from urllib import urlencode
    from urllib2 import Request, urlopen, build_opener
    from urllib2 import ProxyHandler, HTTPBasicAuthHandler, HTTPHandler, HTTPError, URLError

import ast
import json
import sys
import datetime
import calendar
import base64
import math
import time
import os
import subprocess
import socket
import SocketServer
import threading
import logging
import urllib3
import logging
import urllib


from datetime import date

# Nice ANSI colors
CEND    = '\33[0m'
CRED    = '\33[31m'
CGREEN  = '\33[32m'
CYELLOW = '\33[33m'
CBLUE   = '\33[34m'

# Support for OS X Dark Mode
DARK_MODE=os.getenv('BitBarDarkMode',0)


# Daikin bridge code

log = logging.getLogger(__name__)


def parse_basic_info(x):
    integers = ['port', 'err', 'pv']
    booleans = ['pow', 'led']
    parse_data(x, integers=integers, booleans=booleans)
    x['name'] = urllib.parse.unquote(x['name'])
    return x


def parse_sensor_info(x):
    integers = ['err']
    temps = ['hhum', 'htemp', 'otemp']
    parse_data(x, integers=integers, temps=temps)
    return x


ctrl_integers = ['alert', 'mode', 'b_mode']
ctrl_temps = ['shum', 'stemp', 'b_shum']
ctrl_booleans = ['pow']

def parse_control_info(x):
    parse_data(x, integers=ctrl_integers, temps=ctrl_temps, booleans=ctrl_booleans)
    return x

def format_control_info(x):
    format_data(x, integers=ctrl_integers, temps=ctrl_temps, booleans=ctrl_booleans)
    return x


def parse_data(x, integers=[],
                  booleans=[],
                  temps=[]):

    for field in integers:
        try:
            x[field] = int(x[field])
        except ValueError as e:
            log.exception("failed to parse field '{}': {}".format(field, e.message))

    for field in booleans:
        try:
            x[field] = bool(int(x[field]))
        except ValueError as e:
            log.exception("Failed to parse field '{}': {}".format(field, e.message))

    for field in temps:
        try:
            x[field] = parse_temperature(x[field])
        except ValueError:
            log.exception(("Failed to parse field {{'{}':'{}'}}."
                           "A temperature was expected").format(field, x[field]))
            pass


def format_data(x, strict=True,
                integers=[],
                booleans=[],
                temps=[]):

    for field in integers:
        try:
            x[field] = str(int(x[field]))
        except KeyError:
            if not strict:
                pass

    for field in booleans:
        try:
            x[field] = str(int(bool(x[field])))
        except KeyError:
            if not strict:
                pass

    for field in temps:
        try:
            x[field] = str(float(x[field]))
        except KeyError:
            if not strict:
                pass


def parse_temperature(temp):
        try:
            return float(temp)
        except ValueError:
            if temp == '-' or temp == '--':
                return None
            else:
                raise



# Daikin specific code
DSCV_TXT = "DAIKIN_UDP/common/basic_info"
DSCV_PRT = 30050

RET_MSG_OK = b'OK'
RET_MSG_PARAM_NG = b'PARAM NG'
RET_MSG_ADV_NG = b'ADV_NG'

log = logging.getLogger("dainkin_aircon")


class Aircon():

    MODE_AUTO = 0
    MODE_DRY = 2
    MODE_COOL = 3
    MODE_HEAT = 4
    MODE_FAN = 6

    def __init__(self, host):
        self.host = host
        self._http_conn = None

    def get_name(self):
        return self.get_basic_info()['name']

    name = property(get_name)

    def get_mac_address(self):
        return self.get_basic_info()['mac']

    mac_address = property(get_mac_address)

    def get_firmware_version(self):
        return self.get_basic_info()['ver']

    firmware_version = property(get_firmware_version)

    def set_power(self, v):
        self.set_control_info({'pow': v})

    def get_power(self):
        return self.get_control_info()['pow']

    power = property(get_power, set_power)

    def get_target_temp(self):
        return self.get_control_info()['stemp']

    def set_target_temp(self, v):
        self.set_control_info({'stemp': v})

    target_temp = property(get_target_temp, set_target_temp)

    def get_mode(self):
        return self.get_control_info()['mode']

    def set_mode(self, v):
        self.set_control_info({'mode': v})

    mode = property(get_mode, set_mode)

    def get_indoor_temp(self):
        return self.get_sensor_info()['htemp']

    indoor_temp = property(get_indoor_temp)

    def get_outdoor_temp(self):
        return self.get_sensor_info()['otemp']

    outdoor_temp = property(get_outdoor_temp)

    def reboot(self):
        return self.send_request('GET', '/common/reboot')

    def get_raw_basic_info(self):
        return self.send_request('GET', '/common/basic_info')

    def get_basic_info(self):
        return bridge.parse_basic_info(self.get_raw_basic_info())

    def get_raw_sensor_info(self):
        return self.send_request('get', '/aircon/get_sensor_info')

    def get_sensor_info(self):
        return bridge.parse_sensor_info(self.get_raw_sensor_info())

    def set_raw_control_info(self, params, update=True):
        if update:
            cinfo = self.get_raw_control_info()
            minimal_cinfo = {k:cinfo[k] for k in cinfo if k in ['pow','mode','stemp', 'shum','f_rate','f_dir']}
            minimal_cinfo.update(params)
            params = minimal_cinfo
        self.send_request('GET', '/aircon/set_control_info', fields=params)

    def set_control_info(self, params, update=True):
        return self.set_raw_control_info(bridge.format_control_info(params), update)

    def get_raw_control_info(self):
        return self.send_request('GET', '/aircon/get_control_info')

    def get_control_info(self):
        return bridge.parse_control_info(self.get_raw_control_info())

    def send_request(self, method, url, fields=None, headers=None, **urlopen_kw):
        '''Send request to air conditioner

           args and kwargs will be passed to
           `urllib3.request.RequestMethods.request`
        '''
        if self.host is None:
            raise Exception("Cannot send request: host attribute missing")

        if self._http_conn is None:
            self._http_conn = urllib3.PoolManager()

        res = self._http_conn.request(method,
                                      'http://{}{}'.format(self.host, url),
                                      fields=fields,
                                      headers=headers,
                                      **urlopen_kw)
        log.debug("Received response from '{}', data: '{}'".format(self.host,res.data))
        return process_response(res.data)

    def __repr__(self):
        return "<Aircon: '{}'>".format(self.host)


class RespException(Exception):
    pass


def process_response(response):
    '''Transform the air conditioner response into a dictionary

       If the response doesn't starts with
       standard prefix @RESPONSE_PREFIX a RespException will be raised.
    '''
    rsp = response.split(b',')
    if (len(rsp) is 0) or (not rsp[0].startswith(b'ret=')):
        raise RespException("Unrecognized data format for the response")

    ret_msg = rsp[0][4:]
    if ret_msg != RET_MSG_OK:
        if ret_msg == RET_MSG_PARAM_NG:
            raise RespException("Wrong parameters")
        elif ret_msg == RET_MSG_ADV_NG:
            raise RespException("Wrong ADV")
        else:
            raise RespException("Unrecognized return message: '{}'".format(ret_msg))

    # Remove the standard prefix
    rsp = rsp[1:]
    # Transform the dictionary into a response
    rsp = {k.decode():v.decode() for k,v in map(lambda s: s.split(b'='), rsp)}
    return rsp


def discover(waitfor=1,
             timeout=10,
             listen_address="0.0.0.0",
             listen_port=0,
             probe_port=30050,
             probe_address='255.255.255.255',
             probe_attempts=10,
             probe_interval=0.3):

    discovered = {}

    class UDPRequestHandler(SocketServer.BaseRequestHandler):

        def handle(self):
            log.debug("Discovery: received response from {} - '{}'".format(self.client_address[0], self.request[0]))
            resp = process_response(self.request[0])
            host = self.client_address[0]
            discovered[host] = resp

    sckt = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sckt.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sckt.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    server = SocketServer.ThreadingUDPServer((listen_address, listen_port), UDPRequestHandler)
    server.socket = sckt
    srv_addr, srv_port = server.server_address

    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.daemon = True
    log.debug("Discovery: starting UDP server on {}:{}".format(srv_addr, srv_port))
    server_thread.start()

    for i in range(0, probe_attempts):
        log.debug("Discovery: probe attempt {} on {}:{}".format(i, probe_address, probe_port))
        sckt.sendto(DSCV_TXT.encode(), (probe_address, probe_port))
        log.debug("Discovery: sleeping for {}s".format(probe_interval))
        time.sleep(probe_interval)
        if len(discovered) >= waitfor:
            break

    remaining_time = timeout - (probe_interval * probe_attempts)
    if (remaining_time > 0) and (len(discovered) < waitfor):
        log.debug("Discovery: waiting responses for {}s more".format(remaining_time))
        time.sleep(remaining_time)

    server.shutdown()
    server.server_close()

    return discovered

# Logo for both dark mode and regular mode
def app_print_logo():
    if bool(DARK_MODE):
        print ('|image=iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAACBjSFJNAAB6JgAAgIQAAPoAAACA6AAAdTAAAOpgAAA6mAAAF3CculE8AAAACXBIWXMAAA7EAAAOxAGVKw4bAAABWWlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iWE1QIENvcmUgNS40LjAiPgogICA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPgogICAgICA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIgogICAgICAgICAgICB4bWxuczp0aWZmPSJodHRwOi8vbnMuYWRvYmUuY29tL3RpZmYvMS4wLyI+CiAgICAgICAgIDx0aWZmOk9yaWVudGF0aW9uPjE8L3RpZmY6T3JpZW50YXRpb24+CiAgICAgIDwvcmRmOkRlc2NyaXB0aW9uPgogICA8L3JkZjpSREY+CjwveDp4bXBtZXRhPgpMwidZAAABeklEQVQ4EYXSzStEURjH8TuYKBR2Ew2xkWJphIVSspGNrE0UkTVJ3fwB/gp7s1As1GyszI6Nl+SlBgnTNFiQur6/2zlj7m1eTn3mPOc5z3PuPVzHqTA8z1vAi5GsUFY+TZOLNwxhEK/YKV8dylLo4h09dos4Dh1Y/RAKXKi52zbbmVz1QyhwEWhm3YaRmodQtIUcik8mjiKFZyRKDulkrQdt+zmCfnyiXQnmBFbMfMGsMYdlTKEJerMPDKihC09YNQfsEWukoaZjJKFRQAxLUE/cvoX+5zfmgGHiI5xARfoWznEI19RcES8qrtMP4w45P3KcAvM1HhBDB35xiSw08rhV0KAfRiM8P3KcdWZd5x6bmMAZNqAr7DN/Qz3FAxTbcUqgzRTWMIld6E301CiCg1P1182UZlk3Q3f/wUxoL0NuWjl7hfrSAsWRSOSLolnCUeKD0L6u+99DYS/0IY2jFS1m9l/XrG1ujLVq+wKHktDHkkW+hkf2523zHwXDsU5gpTZiAAAAAElFTkSuQmCC')
    else:
        print ('|image=iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAAXNSR0IArs4c6QAAAARnQU1BAACxjwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAFbSURBVDhPjZLNK0RRGMbvRikUGyUaXxsplihTUtJIdrJRGlHkHyBNyc5KzcJmsmNvx0JZsGJhYSOlbHwkH/lajQW/Z3rPdNzudefUr/c973mf55xz7wmC+JFl6dGY/acvcmmN6jP0Qg88wXqlJhK/QJsnSJlhookTt0bslmgSJa7HaKCSk6zS9Ar+zlXM9+AB+j2TZrtiztW6SL6gwQpqXjTRJfEHJmEBRqEadLJP6JamBe5hyQx2THRkokOifqOMPqAJ5k2j71IaWbi2vI94ACfWpLdwAfug76RxBXNOrDgEZ1bQlfKwC9r1G85h0xOdkg/7BrqbihpbJrwhLoNOs2G1d6K+1TFk4gxmWNiGcdCxizACBViBxjgDdwVnXEOiu8tgwt+NXL1/TjBmxVBf0E5hOlxkruvqhOXRQaaHlIY6qLWox6ShuasNWm9n2FiP5RbeErhjfcqJfwHZJFSmRmSsmgAAAABJRU5ErkJggg==')    
    print('---')


# No init needed for Daikin

def init():
    # Here we do the setup
    return

# The main function

def main(argv):

    # get the data for the location      
    try:
       aircos = discover()
    except Exception as e:
       aircos = {}

    if bool(DARK_MODE):
        color = '#FFDEDEDE'
    else:
        color='black'

    app_print_logo()
    prefix = ''

    # print the data for the location
    print ('%sNumber of aircos detected: %s | color=%s' % (prefix, len(aircos), color))
    print ('%s---' % prefix) 
    for airco in aircos.keys():
       print ('%s%s | color=%s' % (prefix, airco, color))
       print ('%s--Turn on | color=%s' % (prefix, color))

    # print ('%s---' % prefix) 


def run_script(script):
    return subprocess.Popen([script], stdout=subprocess.PIPE, shell=True).communicate()[0].strip()


if __name__ == '__main__':
    main(sys.argv)
