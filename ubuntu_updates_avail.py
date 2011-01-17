#!/usr/bin/python3
'''
Check whether there are updates available for Ubuntu (using apt-get).

Will update a file (ubuntu_updates_avail.info) with the information so conky
can read it.

You can run the script directly from conky, with some modifications (print out
instead of writing to file.) This isn't recommended because the script will
take long enough that conky will freeze for a couple of seconds. Also note that
your conky will then require root access. But if you run this via cron and out_file,
only this will get root access.

@note: b/c script is calling apt-get, it requires root access, via sudo. Its
possible to remove the need for sudo by removing the call to 'apt-get update',
but then you'd have to rely on the os to update the local package information
on its own (which it probably already does.)

@note: to change what info appears in your conky, edit `output`

@license
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

@date Jan 15, 2010
@author Matthew Todd
'''

import subprocess
import sys
import re
import logging
import textwrap
from optparse import OptionParser
import os
import time

FAILED_MSG = ' update check failed'
def write_failed_msg(filename):
    with open(filename, 'w') as f:
        f.write(FAILED_MSG)

def program_options():
    '''
    handles program options

    @date Jan 16, 2010
    @author Matthew Todd
    '''
    usage = "usage: %prog [options] <output_file>"
    version_info = textwrap.dedent('''\
        ubuntu_updates_avail Copyright (C) 2011 Matthew A. Todd
        This program is licensed under the GNU GPL v.3. For a full text of the
        license, please see 'COPYING' or GNU's online copy.
        ''')
    
    parser = OptionParser(usage)
    parser.add_option("--version", dest="version",
                        action="store_true", default=False,
                        help='''print version information and quit''')

    parser.add_option("--base_dir", dest="base_dir",
                        action="store", default=".",
                        help="""Location to store output file and log file (if log file isn't given its own directory)""")

    parser.add_option("--log_file", dest="log_file",
                        action="store", default="ubuntu_updates_avail.log",
                        help="""Name of generated log file""")

    parser.add_option("--log_dir", dest="log_dir",
                        action="store", default=None,
                        help="""Location to store the generated log file""")

    parser.add_option("--log_level", dest="log_level",
                        action="store", default="debug",
                        help="""The log level""")

    (options, args) = parser.parse_args()

    if options.version:
        print(version_info)
        sys.exit(0)

    if len(args) != 1:
        parser.error("Incorrect number of arguments")

    return (options, args)

options, args = program_options()
out_file = os.path.abspath(os.path.join(options.base_dir, args[0]))

def setupLogging(directory, filename, level):
    '''
    Create and setup our root logger.

    @param filename String indicating name of the log file to output
    @param directory String indicating directory where to output the log file
    @param level String indicating the log level to use

    @throws InvalidLogLevelError whenever the inputted level is invalid.

    @note this was taken from another one of my personal projects. And no, I'm
    not sure a library is worth it (yet.)

    @date Nov 10, 2010
    @author Matthew Todd
    '''
    log_file = os.path.abspath(os.path.join(directory, filename))

    level = level.upper()
    if level == 'DEBUG':
        log_level = logging.DEBUG
    elif level == 'INFO':
        log_level = logging.INFO
    elif level == 'WARNING':
        log_level = logging.WARNING
    elif level == 'ERROR':
        log_level = logging.ERROR
    elif level == 'CRITICAL' or level == 'FATAL':
        log_level = logging.CRITICAL
    elif level == 'DEFAULT':
        log_level = DEFAULT_LOG_LEVEL
    else:
        #NEXT: more specific exception type
        raise InvalidLogLevelError(level)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    handler = logging.FileHandler(log_file, 'w')
    formatter = logging.Formatter("[%(module)s - %(levelname)s]\t %(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    root_logger.info("Logger created: %s" % time.asctime())

if options.log_dir != None:
    log_dir = options.log_dir
else:
    log_dir = options.base_dir

setupLogging(log_dir, options.log_file, options.log_level)
log = logging.getLogger(__name__)

log.info("out_file = '%s'" % out_file)

try:
    #TODO: check for network availability
    #print special output if network is unavailable

    # call apt-get update
    try:
        retcode = subprocess.call(["sudo", "apt-get", "update", "-qq"])
    except (subprocess.CalledProcessError, OSError) as e:
        log.error("update failed with: %s" % e)
        write_failed_msg(out_file)
        sys.exit(retcode)

    # call and save upgrade --no-act
    try:
        ret = subprocess.check_output(['apt-get', 'upgrade', '--no-act', '-q'])
        upgrade_output= ret.decode()
    except (subprocess.CalledProcessError, OSError) as e:
        log.error("upgrade --no-act failed with: %s" % e)
        write_failed_msg(out_file)
        sys.exit(retcode)

    # parse returned text
    regex = re.compile('([0-9]+) upgraded, ([0-9]+) newly installed, ([0-9]+) to remove and ([0-9]+) not upgraded.')
    match_obj = regex.search(upgrade_output)

    if match_obj == None:
        log.error('regex failed')
        write_failed_msg(out_file)
        sys.exit(retcode)

    output = '''\
     upgrade         %s
     install         %s
     remove          %s
     not upgraded    %s''' % (match_obj.group(1),
                            match_obj.group(2),
                            match_obj.group(3),
                            match_obj.group(4))

    # write out to conky
    with open(out_file, 'w') as f:
        f.write(output)
    log.info('normal exit: %s' % time.asctime())
    sys.exit(0)

except Exception as e:
    log.error("Exception occured: %s" % e)
    write_failed_msg(out_file)
    sys.exit(1)

