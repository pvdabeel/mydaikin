#!/usr/bin/env PYTHONIOENCODING=UTF-8 /Library/Frameworks/Python.framework/Versions/2.7/bin/python
# -*- coding: utf-8 -*-
#
# <xbar.title>MyDaikin</xbar.title>
# <xbar.version>v1.0</xbar.version>
# <xbar.author>pvdabeel@mac.com</xbar.author>
# <xbar.author.github>pvdabeel</xbar.author.github>
# <xbar.desc>Display information about and control your Daikin Emura airco units from the MacOS menubar</xbar.desc>
# <xbar.dependencies>python</xbar.dependencies>
#
# Licence: GPL v3

# Installation instructions: 
# -------------------------- 
# Ensure you have xbar installed https://github.com/matryer/xbar/releases/latest
# Copy this file to your xbar plugins folder and chmod +x the file from your terminal in that folder
# Run xbar


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

from collections import OrderedDict


# Wait till you have discovered at least X units
MY_NUMBER_UNITS=4


from datetime import date

# Nice ANSI colors
CEND    = '\33[0m'
CRED    = '\33[31m'
CGREEN  = '\33[32m'
CYELLOW = '\33[33m'
CBLUE   = '\33[36m'

# Support for OS X Dark Mode                                                    
DARK_MODE=True if os.getenv('XBARDarkMode','false') == 'true' else False  


# The full path to this file                                                    
                                                                                
cmd_path = os.path.realpath(__file__)      


# Pretty printing 

def justify(string):
    return justify(string,10)

def justify(string,number):
    length = len(string)
    quot   = (number - length ) // 4
    rem    = (number - length )  % 4
    return string.ljust(length+rem,' ').ljust(length+rem+quot,'\t')


# Daikin bridge code

log = logging.getLogger(__name__)


def parse_basic_info(x):
    integers = ['port', 'err', 'pv']
    booleans = ['pow', 'led']
    parse_data(x, integers=integers, booleans=booleans)
    x['name'] = urllib.unquote(x['name'])
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
            #log.exception(("Failed to parse field {{'{}':'{}'}}."
            #               "A temperature was expected").format(field, x[field]))
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

logging.basicConfig()
log = logging.getLogger("daikin_airco")


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

    def get_frate(self):
        return self.get_control_info()['f_rate']

    def set_frate(self,v):
        self.set_control_info({'f_rate': v})

    rate = property(get_frate, set_frate)

    def get_fdir(self):
        return self.get_control_info()['f_dir']

    def set_fdir(self,v):
        self.set_control_info({'f_dir': v})

    fdir = property(get_fdir, set_fdir)

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
        return parse_basic_info(self.get_raw_basic_info())

    def get_raw_sensor_info(self):
        return self.send_request('get', '/aircon/get_sensor_info')

    def get_sensor_info(self):
        return parse_sensor_info(self.get_raw_sensor_info())

    def set_raw_control_info(self, params, update=True):
        if update:
            cinfo = self.get_raw_control_info()
            minimal_cinfo = {k:cinfo[k] for k in cinfo if k in ['pow','mode','stemp', 'shum','f_rate','f_dir']}
            minimal_cinfo.update(params)
            params = minimal_cinfo
        self.send_request('GET', '/aircon/set_control_info', fields=params)

    def set_control_info(self, params, update=True):
        return self.set_raw_control_info(format_control_info(params), update)

    def get_raw_control_info(self):
        return self.send_request('GET', '/aircon/get_control_info')

    def get_control_info(self):
        return parse_control_info(self.get_raw_control_info())

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


def discover(waitfor=MY_NUMBER_UNITS,
             timeout=5,
             listen_address="0.0.0.0",
             listen_port=0,
             probe_port=30050,
             probe_address='255.255.255.255',
             probe_attempts=10,
             probe_interval=0.2):

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
        print ('|image=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')
    else:
        print ('|image=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')
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
        color = '#FFFFFE'                                                       
        info_color = '#C0C0C0'                                                  
    else:                                                                       
        color = '#00000E'                                                       
        info_color = '#616161'   


    # CASE 1: command received
    #         form: IP command arg

    if (len(argv) == 4):
        target = Aircon(argv[1])
        if (argv[2] == "set_power"):
            if (argv[3] == '0'):
               target.set_power(False)
            else:
               target.set_power(argv[3])
        elif (argv[2] == "set_target_temp"):
            target.set_target_temp(argv[3])
        elif (argv[2] == "set_frate"):
            target.set_frate(argv[3])
        elif (argv[2] == "set_fdir"):
            target.set_fdir(argv[3])
        elif (argv[2] == "set_mode"):
            target.set_mode(argv[3])
        else: 
            print "Unknown argument, try again."
        return

    # CASE 2: bitbar output

    app_print_logo()
    prefix = ''

    # print the data for the location
    # print ('%sNumber of aircos detected: %s | color=%s' % (prefix, len(aircos), color))
    try:
       base_unit = Aircon(aircos.keys()[0])
       print (u'%sOutside: \t\t\t%s°C | color=%s' % (prefix, base_unit.get_outdoor_temp(), color))
       print ('%s---' % prefix) 
       for airco in aircos.keys():
          airco_unit = Aircon(airco)

          airco_name     = airco_unit.get_name()
          airco_power    = airco_unit.get_power()
          airco_temp_cur = airco_unit.get_indoor_temp()
          airco_temp_tar = airco_unit.get_target_temp()
          airco_mode     = airco_unit.get_mode()
          airco_frate    = airco_unit.get_frate()
          airco_fdir     = airco_unit.get_fdir()

          rmodes = OrderedDict([ ('0','Auto'), ('3','Cooling'), ('4','Heating'), ('6','Ventilating'), ('2','Drying'), ('1','Auto - cooling'), ('7','Auto - heating') ])

          if bool(airco_power):
             if (airco_temp_tar == None):
                print (u'%s%s %s°C %s(%s)%s| color=%s' % (prefix, justify(airco_name,18), airco_temp_cur, CGREEN, rmodes[str(airco_mode)], CEND, color))
             elif (airco_temp_tar == 'M'):
                print (u'%s%s %s°C %s(%s)%s| color=%s' % (prefix, justify(airco_name,18), airco_temp_cur, CGREEN, rmodes[str(airco_mode)], CEND, color))
             elif (airco_temp_cur >= airco_temp_tar):
                print (u'%s%s %s°C %s-> %s°C%s (%s)| color=%s' % (prefix, justify(airco_name,18), airco_temp_cur, CBLUE, airco_temp_tar, CEND, rmodes[str(airco_mode)], color))
             else:
                print (u'%s%s %s°C %s-> %s°C%s (%s)| color=%s' % (prefix, justify(airco_name,18), airco_temp_cur, CRED, airco_temp_tar, CEND, rmodes[str(airco_mode)], color))
             print ('%s--Turn off | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, cmd_path, airco, 'set_power', 0, color))
             print ('%s--Turn off | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, cmd_path, airco, 'set_power', 0, color))
          else:
             print (u'%s%s %s°C | color=%s' % (prefix, justify(airco_name,18), airco_temp_cur, color))
             print ('%s--Turn on | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, cmd_path, airco, 'set_power', 1, color))
             print ('%s--Turn on | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, cmd_path, airco, 'set_power', 1, color))


          print ('%s-----' % prefix) 
          print ('%s--Mode | color=%s' % (prefix, color))
          modes = OrderedDict([ ('auto','0'), ('cool','3'), ('heat','4'), ('fan','6'), ('dry','2') ])
          for mode in modes.keys():
             if (modes[str(mode)] == str(airco_mode)):
                print (u'%s----%s | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, mode, cmd_path, airco, 'set_mode', modes[str(mode)], color))
                print (u'%s----%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, mode, cmd_path, airco, 'set_mode', modes[str(mode)], color))
             else:
                print (u'%s----%s | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, mode, cmd_path, airco, 'set_mode', modes[str(mode)], info_color))
                print (u'%s----%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, mode, cmd_path, airco, 'set_mode', modes[str(mode)], info_color))
 

          print ('%s--Temperature | color=%s' % (prefix, color))
          for temperature in ['18.0','19.0','20.0','21.0','22.0','23.0','24.0','25.0']:
             if (str(temperature) == str(airco_temp_tar)):
                print (u'%s----%s°C | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, temperature, cmd_path, airco, 'set_target_temp', temperature, color))
                print (u'%s----%s°C | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, temperature, cmd_path, airco, 'set_target_temp', temperature, color))
             else:
                print (u'%s----%s°C | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, temperature, cmd_path, airco, 'set_target_temp', temperature, info_color))
                print (u'%s----%s°C | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, temperature, cmd_path, airco, 'set_target_temp', temperature, info_color))

          print ('%s--Fan | color=%s' % (prefix, color))
          print ('%s----Rate | color=%s' % (prefix, color))
          frates = OrderedDict([ ('auto','A'), ('silent','B'), ('1','3'), ('2','4'), ('3','5'), ('4','6'), ('5','7') ])
          for frate in frates.keys():
             if (frates[str(frate)] == airco_frate):
                print (u'%s------%s | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, frate, cmd_path, airco, 'set_frate', frates[str(frate)], color))
                print (u'%s------%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, frate, cmd_path, airco, 'set_frate', frates[str(frate)], color))
             else:
                print (u'%s------%s | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, frate, cmd_path, airco, 'set_frate', frates[str(frate)], info_color))
                print (u'%s------%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, frate, cmd_path, airco, 'set_frate', frates[str(frate)], info_color))
          print ('%s----Direction | color=%s' % (prefix, color))
          fdirs = OrderedDict([ ('none','0'), ('vertical','1'), ('horizontal','2'), ('3D','3') ])
          for fdir in fdirs.keys():
             if (fdirs[str(fdir)] == airco_fdir):
                print (u'%s------%s | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, fdir, cmd_path, airco, 'set_fdir', fdirs[str(fdir)], color))
                print (u'%s------%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, fdir, cmd_path, airco, 'set_fdir', fdirs[str(fdir)], color))
             else:
                print (u'%s------%s | refresh=true terminal=false shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, fdir, cmd_path, airco, 'set_fdir', fdirs[str(fdir)], info_color))
                print (u'%s------%s | refresh=true alternate=true terminal=true shell="%s" param1=%s param2=%s param3=%s color=%s' % (prefix, fdir, cmd_path, airco, 'set_fdir', fdirs[str(fdir)], info_color))



    except Exception as e:
       print (e)
       print ('%sNo Daikin airco detected | color=%s' % (prefix, color))


if __name__ == '__main__':
    main(sys.argv)
