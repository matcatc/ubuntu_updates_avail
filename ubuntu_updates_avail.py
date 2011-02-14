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

@note
b/c script is calling apt-get, it requires root access, via sudo. Its
possible to remove the need for sudo by removing the call to 'apt-get update',
but then you'd have to rely on the os to update the local package information
on its own (which it probably already does.)

@note
see --help output (or look in the code below) to see what command line
options are available.

@note
Because of the nature of the script, it is very difficult to test. I think I
probably could write unit tests for all of it by extracting the subprocess
calls to their own objects then mocking them, but doing so might not be
worthwhile. Anyways, until I get testing setup, the script is not going to be
extensively tested. So bug reports will be very much appreciated. If I don't
see the bug when running the script myself, then I am relient on you and other
users to report them to me, so please do.

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

@date Jan 15, 2011
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


###
#### macros
###

DEFAULT_OUTPUT_TEMPLATE = '''\
 as of {time}:
 upgrade            {upgrade}
 install            {install}
 remove             {remove}
 not upgraded       {not_upgraded}'''
 
FAILED_MSG = ' update check failed'             # generic failure msg
NO_NETWORK_MSG = ' no network available'

DEFAULT_SERVER_ADDRESS = 'us.archive.ubuntu.com'

NO_ERROR = 0

## The key values to this dict must be the same as the names of the exceptions
## to which they are related
ERROR_CODES = {
                'default' : 10,
                'CustomException' : 11,
                'NoNetworkError' : 12,
                'UpdateError' : 13,
                'UpgradSimulError' : 14,
                'UpgradeOutputParseError' : 15,
                'GenerateOutputError' : 16,
                }

###
#### exceptions
###
class CustomException(Exception):
    '''
    Base class for our custom exceptions.

    TODO: better name

    @date Feb 13, 2011
    @author Matthew Todd
    '''
    def __init__(self, error):
        '''
        @param error the error giving more details as to the exception
        '''
        self.error = error

        self.key = self.__class__.__name__

    def __str__(self):
        '''
        Default str() implementation.

        Sub classes will likely want to override this as using the class name
        is somewhat terse and not very 'informal'.
        '''
        return "%s: %s" % (self.__class__.__name__, self.error)

    def __repr__(self):
        '''
        Defines default repr() implementation.

        As long as subclasses don't have any other attributes besides error,
        then they don't need to override this implementation.
        '''
        return "%s(error=%r)" % (self.__class__.__name__, self.error)

class NoNetworkError(CustomException):
    '''
    Error when there is no network connection.

    @date Feb 12, 2011
    @author Matthew Todd
    '''
    def __init__(self, error):
        '''
        @param error the error indicating the network is unavailable
        '''
        self.error = error

        self.key = self.__class__.__name__

    def __str__(self):
        return "No network available: %s" % self.error

class UpdateError(CustomException):
    '''
    Error when the call to apt-get update failed.

    @date Feb 12, 2011
    @author Matthew Todd
    '''
    def __init__(self, error):
        '''
        @param error the exception that was thrown when we tried to run update
        '''
        self.error = error

        self.key = self.__class__.__name__

    def __str__(self):
        return "Call to apt-get update failed: %s" % self.error

class UpgradeSimulError(CustomException):
    '''
    Error for when the upgrade simulation failed.

    @date Feb 12, 2011
    @author Matthew Todd
    '''
    def __init__(self, error):
        '''
        @param error the exception raised when we tried to run the simulated upgrade
        '''
        self.error = error

        self.key = self.__class__.__name__

    def __str__(self):
        return "Upgrade simulation failed: %s" % e

class UpgradeOutputParseError(CustomException):
    '''
    Error for when the upgrade output parsing failed

    @date Feb 12, 2011
    @author Matthew Todd
    '''
    def __init__(self, error):
        '''
        @param error the reason that we failed
        '''
        self.error = error

        self.key = self.__class__.__name__

    def __str__(self):
        return "Upgrade output parseing failed: %s" % e

class GenerateOutputError(CustomException):
    '''
    Error for when we were unable to generate the output.

    @date Feb 12, 2011
    @author Matthew Todd
    '''
    def __init__(self, error):
        '''
        @param error the reason that we failed
        '''
        self.error = error

        self.key = self.__class__.__name__


    def __str__(self):
        return "Generation of output failed: %s" % e


###
#### program options
###
def program_options():
    '''
    handles program options

    @date Jan 16, 2011
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
                    {install}, {remove}, {not_upgraded}, {time}, {upgradable} along with the
                    normal formatting syntax.
                    
                    upgrade, install, remove, not_upgraded are strait from apt-get upgrade output.
                    
                    time is the current time (full asctime)
                    
                    upgradable is the sum of upgrade and not_upgraded. This is likely what you'll
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

def compute_out_file(base_dir, filename):
    '''
    Computes the file out_file path/filename.

    @date Feb 11, 2011
    @author Matthew Todd
    '''
    return os.path.abspath(os.path.join(options.base_dir, args[0]))

def get_template(template_file, base_dir):
    '''
    Gets the template from the file. If no file, then uses default.

    @date Feb 11, 2011
    @author Matthew Todd
    '''
    if options.template_file:
        template_file = os.path.abspath(os.path.join(options.base_dir, options.template_file))
        with open(template_file, 'r') as f:
            return f.read()
    else:
        return DEFAULT_OUTPUT_TEMPLATE

# we do this here so that we have what we need to setup logging.
options, args = program_options()


###
#### logging
###
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

def compute_log_dir(log_dir, base_dir):
    '''
    Computes the directory where the log file(s) are to be stored.

    Chooses between log_dir and base_dir. If log_dir isn't None, then its log_dir.

    @date Feb 11, 2011
    @author Matthew Todd
    '''
    if options.log_dir != None:
        return options.log_dir
    else:
        return options.base_dir

# we do this here b/c it makes sense for the logger to be available to all funcs,
#  without having to pass it to each one
setupLogging(compute_log_dir(options.log_dir, options.base_dir), options.log_file, options.log_level)
log = logging.getLogger(__name__)


###
#### helper functions
###
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
    else:
        log.info('not writing error to output file b/c no_error_output is set')

def check_network(server_address = DEFAULT_SERVER_ADDRESS):
    '''
    Determine whether the network (internet) is available.

    Raises an exception to signal that the network is down.

    - checks routing table for default route
    - checks if the ubuntu servers are reachable

    @note Hasn't been tested extensively due to the fact that its hard to
    similate most condtions.

    @param server_address the ubuntu server to check. Defaults to the main us server.
    @throws NoNetworkError
    @return None
    @date Jan 27, 2011
    @author Matthew Todd
    '''
    # check for default route in routing table
    output = subprocess.getoutput('/sbin/route -n | grep -c "^0\.0\.0\.0"')
    if int(output) == 0:
        raise NoNetworkError("no default route in table")

    # ping ubuntu servers
    ret_code, _ = subprocess.getstatusoutput('ping -q -c 3 %s' % server_address)
    if ret_code > 0:
        raise NoNetworkError("ping failed with return code: %d" % ret_code)

def call_update():
    '''
    Calls apt-get update.

    Raises an exception if the update failed.

    @throws UpdateFailedError
    @return None
    @date Feb 12, 2011
    @author Matthew Todd
    '''
    try:
        subprocess.check_call(["sudo", "apt-get", "update", "-qq"])
    except (subprocess.CalledProcessError, OSError) as e:
        log.error("update failed with: %s" % e)
        raise UpdateError(e)

def get_upgrade_output():
    '''
    Gets the output from the simulated upgrade.

    Note that this is a SIMULATION (hence the --no-act.) Also note that this
    doesn't use root priveleges, so its definitely not going to upgrade.

    @throws UpgradeSimulError
    @return the output string from the simulated upgrade
    @date Feb 12, 2011
    @author Matthew Todd
    '''
    try:
        ret = subprocess.check_output(['apt-get', 'upgrade', '--no-act', '-q'])
        return ret.decode()
    except (subprocess.CalledProcessError, OSError) as e:
        log.error("upgrade --no-act failed with: %s" % e)
        raise UpgradeSimulError(e)

def parse_upgrade_output(upgrade_output):
    '''
    Parse/screen scrape the output of the simulated upgrade.

    Uses regex, hence the return type.

    @throws UpgradeOutputParseError
    @returns a regex-match-object
    @date Feb 12, 2011
    @author Matthew Todd
    '''
    regex = re.compile('([0-9]+) upgraded, ([0-9]+) newly installed, ([0-9]+) to remove and ([0-9]+) not upgraded.')
    match_obj = regex.search(upgrade_output)

    if match_obj == None:
       raise UpgradeOutputParseError('regex failed')

    return match_obj

def generate_output(template, template_dict):
    '''
    Generates the output from the given template and its dict.

    @throws GenerateOutputError
    @return the output string
    @date Feb 12, 2011
    @author Matthew Todd
    '''
    try:
        out_template = get_template(options.template_file, options.base_dir)
        return out_template.format(**template_dict)
    except KeyError as e:
        raise GenerateOutputError('unknown identifier/placeholder: %s' % e)

def create_template_dict(match_obj):
    '''
    Create the template dict to be used to substitute in real values.

    @param match_obj the regex match object from "sudo apt-get upgrade ...". Contains the data to use
        to fill the dict.
    @return dictionary with the template placeholder's as keys and their apporopriate values (from match_obj)
    @date Feb 11, 2011
    @author Matthew Todd
    '''
    upgrade = match_obj.group(1)
    install = match_obj.group(2)
    remove = match_obj.group(3)
    not_upgraded = match_obj.group(4)
    cur_time = time.asctime()
    upgradable = str(int(upgrade) + int(not_upgraded))

    return { 'upgrade'      : upgrade,
            'install'       : install,
            'remove'        : remove,
            'not_upgraded'  : not_upgraded,
            'time'          : cur_time,
            'upgradable'    : upgradable,}

###
#### main
###
def main():
    '''
    Main function.

    returns the exit code.

    @date Feb 11, 2011
    @author Matthew Todd
    '''
    out_file = compute_out_file(options.base_dir, args[0])
    log.info("out_file = '%s'" % out_file)

    try:
        check_network()

        call_update()

        upgrade_output = get_upgrade_output()

        match_obj = parse_upgrade_output(upgrade_output)

        template_dict = create_template_dict(match_obj)

        template = get_template(options.template_file, options.base_dir)

        output = generate_output(template, template_dict)

        write_msg(out_file, output, is_error=False)

        log.info('normal exit: %s' % time.asctime())
        return NO_ERROR


    except NoNetworkError as e:
        log.error(e)
        write_msg(out_file, NO_NETWORK_MSG, is_error=True)
        return ERROR_CODES[e.key]

    except UpdateError as e:
        log.error(e)
        write_msg(out_file, FAILED_MSG, is_error=True)
        return ERROR_CODES[e.key]

    except UpgradeSimulError as e:
        log.error(e)
        write_msg(out_file, FAILED_MSG, is_error=True)
        return ERROR_CODES[e.key]

    except UpgradeOutputParseError as e:
        log.error(e)
        write_msg(out_file, FAILED_MSG, is_error=True)
        return ERROR_CODES[e.key]

    except GenerateOutputError as e:
        log.error(e)
        write_msg(out_file, FAILED_MSG, is_error=True)
        return ERROR_CODES[e.key]

    except CustomException as e:
        log.error(e)
        write_msg(out_file, FAILED_MSG, is_error=True)
        return ERROR_CODES[e.key]

    except Exception as e:
        log.error(e)
        write_msg(out_file, FAILED_MSG, is_error=True)
        return ERROR_CODES['default']

if __name__ == "__main__":
    sys.exit(main())
