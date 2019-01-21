#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#    Potiron -  Normalize, Index, Enrich and Visualize Network Capture
#    Copyright (C) 2018-2019 Christian Studer
#    Copyright (C) 2018-2019 CIRCL Computer Incident Response Center Luxembourg (smile gie)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

from glob import glob
from pathlib import Path
from potiron.potiron import check_program, create_dir
from potiron.potiron_parameters import fetch_parameters
from potiron.potiron_tshark import standard_process
from potiron.potiron_isn_tshark import isn_process
import argparse
import datetime
import os
import redis
import subprocess
import sys


def define_tshark_filter(tsharkfilter):
    to_return = tsharkfilter[0] if len(tsharkfilter) == 0 else " && ".join(tsharkfilter)
    return to_return


def fetch_files(directory: Path):
    to_return = []
    try:
        for dir_ in directory.iterdir():
            if dir_.is_file():
                if any([dir_.name.endswith('cap'), dir_.name.endswith('cap.gz')]):
                    to_return.append(str(dir_))
            else:
                to_return.extend(fetch_files(dir_))
    except (NotADirectoryError, FileNotFoundError):
        for file_ in glob(str(directory)):
            to_return.append(file_)
    return to_return


def _get_function_score(isn):
    score = 0
    if isn:
        sccore += 1
    return str(score)


if __name__ == '__main__':
    # If tshark is not installed, exit and raise the error
    if not check_program('tshark'):
        raise OSError("The program tshark is not installed")
    # FIXME Put in config file

    # Parameters parser
    parser = argparse.ArgumentParser(description="Start the tool tshark and store packets data in redis.")
    parser.add_argument("-i", "--input", type=str, nargs='+', required=True, help="Pcap or compressed pcap filename")
    parser.add_argument("-c", "--console", action='store_true', help="Log output also to console")
    parser.add_argument("-ff", "--fieldfilter", nargs='+',help='Parameters to filter fields to display (ex: "tcp.srcport udp.srcport")')
    parser.add_argument("-o", "--outputdir", type=str, nargs=1, help="Output directory where the json documents will be stored")
    parser.add_argument("-tf", "--tsharkfilter", type=str, nargs='+', help='Tshark Filter (with wireshark/tshark synthax. ex: "ip.proto == 6")')
    parser.add_argument('-u','--unix', type=str, nargs=1, required=True, help='Unix socket to connect to redis-server')
    parser.add_argument('-ck', '--combined_keys', action='store_true', help='Set if combined keys should be used')
    parser.add_argument('-ej', '--enable_json', action='store_true', help='Enable storage into json files')
    parser.add_argument('--isn', action='store_true', help='Store ISN values of packets instead of storing the standard data.')
    args = parser.parse_args()
    logconsole = args.console
    usocket = args.unix[0]
    try:
        red = redis.Redis(unix_socket_path=usocket)
    except redis.ConnectionError as e:
        sys.exit(f"Could not connect to redis. {e}")
    for arg in args.input:
        if os.path.exists(arg) is False:
            sys.stderr.write(f"The filename {arg} was not found\n")
            sys.exit(1)
    input_directory = [Path(arg) for arg in args.input]
    files = [filename for directory in input_directory for filename in fetch_files(directory)]

    isn = args.isn
    fieldfilter = args.fieldfilter

    if isn and fieldfilter is not None:
        print("If you use '--isn', the field filter parameter will be ignored.")
    elif not isn and fieldfilter is None:
        fieldfilter = []

    tsharkfilter = define_tshark_filter(args.tsharkfilter) if args.tsharkfilter is not None else ""

    enable_json = args.enable_json

    if not enable_json:
        rootdir = 'None'
    else:
        if args.outputdir is None:
            sys.stderr.write("You should specify an output directory.\n")
            sys.exit(1)
        rootdir = args.outputdir[0]
        create_dir(rootdir)
        if os.path.isdir(rootdir) is False:
            sys.stderr.write("The root directory is not a directory\n")
            sys.exit(1)

    ck = args.combined_keys

    parameters = {'rootdir': rootdir, 'tshark_filter': tsharkfilter, 'red': red, 'isn': isn,
                  'enable_json': str(enable_json), 'logconsole': str(logconsole)}
    if not isn:
        parameters.update({'field_filter': fieldfilter, 'ck': str(ck)})
    fetch_parameters(**parameters)
    try:
        globals()[_get_function_score(isn)](red, files)
    except KeyError:
        sys.stderr.write("Invalid content option.")
