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

DEFAULT_OUTPUT_TEMPLATE = '''\
 as of {time}:
 upgrade            {upgrade}
 install            {install}
 remove             {remove}
 not upgraded       {not_upgraded}'''
 
FAILED_MSG = ' update check failed'             # generic failure msg
NO_NETWORK_MSG = ' no network available'

DEFAULT_SERVER_ADDRESS = 'us.archive.ubuntu.com'

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
    
    template_help = textwrap.dedent('''\
                    Template/format for output file. Option specifies a file,
                    which contains the template. The template is a python
                    string that will have format() called on it. You can use
                    the following identifiers/placeholders: {upgrade},
                    {install}, {remove}, {not_upgraded}, {time}, {upgradeable} along with the
                    normal formatting syntax.
                    
                    upgrade, install, remove, not_upgraded are strait from apt-get upgrade output.
                    
                    time is the current time (full asctime)
                    
                    upgradeable is the sum of upgrade and not_upgraded. This is likely what you'll
                    want to use most of the time.''')

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

    parser.add_option("--template", dest="template_file",
                        action="store", default=None,
                        help=template_help)

    parser.add_option("--no_error_output", dest="no_error_output",
                        action="store_true", default=False,
                        help='''Do not update output file with errors. If
                            update was unsucessful, leave old file untouched.''')

    (options, args) = parser.parse_args()

    if options.version:
        print(version_info)
        sys.exit(0)

    if len(args) != 1:
        parser.error("Incorrect number of arguments")

    return (options, args)

options, args = program_options()
out_file = os.path.abspath(os.path.join(options.base_dir, args[0]))
if options.template_file:
    with open(options.template_file, 'r') as f:
        out_template = f.read()
else:
    out_template = DEFAULT_OUTPUT_TEMPLATE

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
    class InvalidLogLevelError(Exception):
        '''
        Invalid log level.
        '''
        def __init__(self, lvl):
            super().__init__()
            self.log_level = lvl

        def __str__(self):
            return "Invalid Log Level: %s" % self.log_level

        def __repr__(self):
            return str(self)

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

def write_msg(filename, msg, is_error):
    '''
    This function writes out the given message to the output file.

    This function truncates the output file prior to writing out the new
    message. So the last call to this function will be overwritten. Thus if you
    want to write out multiple pieces of data, combine them into one string and
    then write it out using this function.

    @param filename filename of the output file.
    @param msg the message to write out to the output file. This is what will
        be displayed to the user.
    @param is_error whether the output is an error msg. This allows us to shut
        off error messages to the output file, should we so desire.
    @date Jan 17, 2011
    @author Matthew Todd
    '''
    if not (options.no_error_output and is_error):
        with open(filename, 'w') as f:
            f.write(msg)

def network_unavailable(server_address = DEFAULT_SERVER_ADDRESS):
    '''
    Determine whether the network (internet) is available.

    - checks routing table for default route
    - checks if the ubuntu servers are reachable

    @note Hasn't been tested extensively due to the fact that its hard to
    similate most condtions.

    @param server_address the ubuntu server to check. Defaults to the main us server.
    @return True if the network is unavailable
    @date Jan 27, 2010
    @author Matthew Todd
    '''
    try:
        # check for default route in routing table
        output = subprocess.getoutput('/sbin/route -n | grep -c "^0\.0\.0\.0"')
        if int(output) == 0:
            log.info("no default route in table")
            return True

        # ping ubuntu servers
        subprocess.check_output(['ping', '-q', '-c', '3', server_address])
    except (subprocess.CalledProcessError) as e:
        log.info("no network connection: %s" % e)
        return True

    return False

try:
    if network_unavailable():
        log.error("network unavailable")
        write_msg(out_file, NO_NETWORK_MSG, is_error=True)
        sys.exit(3)

    # call apt-get update
    try:
        retcode = subprocess.call(["sudo", "apt-get", "update", "-qq"])
    except (subprocess.CalledProcessError, OSError) as e:
        log.error("update failed with: %s" % e)
        write_msg(out_file, FAILED_MSG, is_error=True)
        sys.exit(retcode)

    # call and save upgrade --no-act
    try:
        ret = subprocess.check_output(['apt-get', 'upgrade', '--no-act', '-q'])
        upgrade_output= ret.decode()
    except (subprocess.CalledProcessError, OSError) as e:
        # most likely: permissions error
        log.error("upgrade --no-act failed with: %s" % e)
        write_msg(out_file, FAILED_MSG, is_error=True)
        sys.exit(retcode)

    # parse returned text
    regex = re.compile('([0-9]+) upgraded, ([0-9]+) newly installed, ([0-9]+) to remove and ([0-9]+) not upgraded.')
    match_obj = regex.search(upgrade_output)

    if match_obj == None:
        log.error('regex failed')
        write_msg(out_file, FAILED_MSG, is_error=True)
        sys.exit(retcode)

    upgrade = match_obj.group(1)
    not_upgraded = match_obj.group(4)
    upgradeable = str(int(upgrade) + int(not_upgraded))
    template_dict = { 'upgrade' : upgrade,
                        'install' : match_obj.group(2),
                        'remove' : match_obj.group(3),
                        'not_upgraded' : not_upgraded,
                        'time' : time.asctime(),
                        'upgradeable' : upgradeable,}

    try:
        output = out_template.format(**template_dict)
    except KeyError as e:
        write_msg(out_file, FAILED_MSG, is_error=True)
        log.error('output formatting failed: unknown identifier/placeholder: %s' % e)
        sys.exit(2)

    # write out to conky
    write_msg(out_file, output, is_error=False)

    log.info('normal exit: %s' % time.asctime())
    sys.exit(0)

except Exception as e:
    log.error("Exception occured: %s" % e)
    write_msg(out_file, FAILED_MSG, is_error=True)
    sys.exit(1)

