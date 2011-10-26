#!/usr/bin/python3
'''
@mainpage
@section Welcome
@par
These pages contain the little information I have bothered to write down
regarding the programmaing details. Note that although this is very much geared
towards developers, it could contain information that would be useful to
end-users.

@section Program The Program in Brief
@par
I wrote this program to display update information in my conky script.  The
program checks whether there are updates available using apt-get and output to
a file.


@section Requirements
- python 3
- apt-get

@section Documenation Building Documentation
@par
Run build_documentation.sh. It will build all the documentation in the doc
subdirectory. In order to get doxygen working better with python, I added the
following to my Doxyfile (included in the repository):

@code
INPUT_FILTER = “python /path/to/doxypy.py”
@endcode

Where doxypy.py is from: http://code.foosel.org/doxypy

You can remove the INPUT_FILTER line if you want to keep from having to
download and setup doxypy. The output might not be as pretty, though.

@section Links
 - Homepage: http://matcatc.github.com/ubuntu_updates_avail/
 - Github: https://github.com/matcatc/ubuntu_updates_avail

@section License
@verbatim
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
@endverbatim

@date Jan 15, 2011
@author Matthew Todd

@page Testing
@section Testing
@par
Because of the nature of the script, it is very difficult to test. I could
write unit tests for all of it by extracting the subprocess calls to their own
objects then mocking them, but doing so might not be worthwhile.

@par
Anyways, until I get testing setup, the script is not going to be extensively
tested, so bug reports will be very much appreciated. If I don't see the bug
when running the script myself, then I am relient on you and other users to
report them to me, so please do.

@date Apr 17, 2011
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

## The key values to this dict must be the same as the names of the exceptions
## to which they are related
FAILED_MSG = ' update check failed'             # generic failure msg
ERROR_MSGS = {  'default'                   : FAILED_MSG,
                'CustomException'           : FAILED_MSG,
                'NoNetworkError'            : ' no network available',
                'UpdateError'               : ' failed to update package info',
                'UpgradSimulError'          : ' failed to simulate upgrade',
                'UpgradeOutputParseError'   : ' failed to parse simulated upgrade output',
                'GenerateOutputError'       : ' failed to generate outut',
                }

###
#### exceptions
###
class CustomException(Exception):
    '''
    Base class for our custom exceptions.

    TODO: better name

    So that we can catch this custom exception type and handle all of our exceptions dynamically.

    @date Feb 13, 2011
    @author Matthew Todd
    '''
    def __init__(self, error):
        '''
        self.key is the key used to index into the exception related
        dictionaries to get their info (return code, etc.)

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
        super().__init__(error)

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
        super().__init__(error)

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
        super().__init__(error)

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
        super().__init__(error)

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
        super().__init__(error)

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
    usage = "usage: %prog [options] <output_file/->"
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

    num_update_checks_help = textwrap.dedent('''\
            Number of times to try apt-get update before failing. Default is 1.
            0 tries implies that it is not to update.''')

    no_update_help = textwrap.dedent('''\
            Do not update. Note that this option conflicts with
            --num_update_checks (for obvious reasons). If both are specified,
            which one is used isn't specified.''')

    parser = OptionParser(usage)
    parser.add_option("--version", dest="version",
                        action="store_true", default=False,
                        help='''print version information and quit''')

    parser.add_option("--base_dir", dest="base_dir",
                        action="store", type="string", default=".",
                        help="""Location to store output file and log file (if log file isn't given its own directory)""")

    parser.add_option("--log_file", dest="log_file",
                        action="store", type="string", default="ubuntu_updates_avail.log",
                        help="""Name of generated log file""")

    parser.add_option("--log_dir", dest="log_dir",
                        action="store", type="string", default=None,
                        help="""Location to store the generated log file""")

    parser.add_option("--log_level", dest="log_level",
                        action="store", type="string", default="debug",
                        help="""The log level""")

    parser.add_option("--template", dest="template_file",
                        action="store", type="string", default=None,
                        help=template_help)

    parser.add_option("--time_format", dest="time_format",
                        action="store", type="string", default='%c',
                        help='''Define the format of the time placeholder to be used in the template.''')

    parser.add_option("--max_width", dest="max_width",
                        action="store", type="int", default=0,
                        help='''max width of the output.''')

    parser.add_option("--no_error_output", dest="no_error_output",
                        action="store_true", default=False,
                        help='''Do not update output file with errors. If
                            update was unsucessful, leave old file untouched.''')

    parser.add_option("-c", "--num_update_checks", dest="num_update_checks",
                        action="store", type="int", default=1,
                        help=num_update_checks_help)

    parser.add_option("--sleep_period", dest="sleep_period",
                        action="store", type="int", default=0,
                        help="how long to sleep between update tries.")

    parser.add_option("--no_update", dest="num_update_checks",
                        action="store_const", const=0,
                        help=no_update_help)

    parser.add_option("--no_root", dest="no_root",
                        action="store_true", default=False,
                        help='''Disable all operations requiring root priveleges.''')

    parser.add_option("--network_check", dest="network_check",
                        action="store_true", default=False,
                        help='''Enable network checking. Will verify network's
                        prescence before trying to update. Note that network
                        check's accuracy cannot be guaranteed.''')

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

    If the outfile is '-', use stdout.

    @param base_dir String The directory from which to base the out file.
    @param filename String the name of the out file. Can contain path information as well.
    @date Feb 11, 2011
    @author Matthew Todd
    '''
    if filename.strip() == '-':
        return '-'
    else:
        return os.path.abspath(os.path.join(options.base_dir, args[0]))

def get_template(template_file, base_dir):
    '''
    Gets the template from the file. If no file, then uses default.

    @param template_file String filename of the template file. Can contain path information.
    @param base_dir String directory to base the file off of.
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

    @note We have this function to determine whether we're using a special
    directory for logging and to use it if so. We might want to log to a common
    directory (e.g: /var/log or similar).

    @param log_dir String directory from which to base the log file. Can be None to indicate to use the default (base_dir).
    @param base_dir String directory from which most/all of the files are based. The default for logging.
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

log.info("options = %r, args = %r" % (options, args))           # never know when we might need this info


###
#### decorators
###

def option_no_root(f):
    '''
    Decorator that handles no root option stuff.

    If no_root it set, then we're not going to use f(). Instead we'll log that
    its not being run due to insufficient privileges and return None. If
    no_root is not set, then we'll just run f normally.

    This way we only check no_root once, during decoration. So we can call a
    decorated function many times without having to waste time checking. Also,
    its much easier to add the no_root check to functions as we just decorate
    them.

    Uses options.no_root

    @note
    This decorator will prevent the entire function from running based on
    the value of no_root. This requires that everything in the function
    shouldn't run if it is set. Therefore functions decorated with this
    decorator should be sufficiently small/precise as to only contain that
    which requires root privileges and its immediately related code.

    @param f function to decorate
    @date Mar 23, 2011
    @author Matthew Todd
    '''
    if options.no_root:
        def g(*args):
            log.info("not running '%s' b/c of insufficient privileges (no_root)." % f.__name__)
            return None
        return g

    else:
        return f

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

    Although this may be inconvenient, as we'll have to create the full output
    before writing, this way we can ensure that output is only outputted if its
    supposed to be (no_error_output option). Anyways, as this program stands,
    there is only really the need to write to file once. Plus normally
    everything is buffered so it'll end up writing all at once to disk in the
    end.

    @param filename String filename of the output file.
    @param msg String the message to write out to the output file. This is what will
        be displayed to the user.
    @param is_error Boolean whether the output is an error msg. This allows us to shut
        off error messages to the output file, should we so desire.
    @date Jan 17, 2011
    @author Matthew Todd
    '''
    if not (options.no_error_output and is_error):
        if filename == '-':
            print(msg)
        else:
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

    @note I'm considering removing this function b/c its not very effective.
    Its given me several false positives and doesn't offer more than multiple
    update checks. Please give me feedback if you have any ideas as how to make
    it more effective or if you want me to keep it.

    @param server_address String the ubuntu server to check. Defaults to the main us server.
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

@option_no_root
def call_update(num_update_checks, sleep_period):
    '''
    Calls apt-get update.

    Raises an exception if the update failed.

    @param num_update_checks Int The number of times to try updating. Negative numbers are equivalent to 0.
    @param sleep_period Int How long to sleep between update tries. Numbers <= 0 means no sleeping.
    @throws UpdateFailedError
    @return None
    @date Feb 12, 2011
    @author Matthew Todd
    '''
    def ordinal(num):
        '''
        Return the ordinal of the number

        Placeholder function.

        @date Feb 25, 2011
        @author Matthew Todd
        '''
        return num

    if num_update_checks < 1:
        log.info("number of times to update is %d (less than 1), therefore not updating" % num_update_checks)
        return

    if sleep_period < 0:
        sleep_period = 0

    fail_count = 0
    while True:
        try:
            subprocess.check_call(["sudo", "apt-get", "update", "-qq"])
            break
        except (subprocess.CalledProcessError, OSError) as e:
            fail_count += 1
            log.error("update failed for %d try with: %s" % (ordinal(fail_count), e))

            if fail_count >= num_update_checks:
                raise UpdateError(e)

            log.info("sleeping for %d seconds before trying to update again" % sleep_period)
            time.sleep(sleep_period)        # sleep before trying to update again

    log.info("update succeeded")

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

    Uses regex, hence the return type. Would like to return something that is
    independent of implementation. But there is no reason to add extra code
    complexity when we don't need it, so I'm going to leave this be for the
    moment.

    @throws UpgradeOutputParseError
    @param upgrade_output String the output from the simulated (or actual) apt-get upgrade.
    @returns a regex-match-object
    @date Feb 12, 2011
    @author Matthew Todd
    '''
    regex = re.compile('([0-9]+) upgraded, ([0-9]+) newly installed, ([0-9]+) to remove and ([0-9]+) not upgraded.')
    match_obj = regex.search(upgrade_output)

    if match_obj == None:
       raise UpgradeOutputParseError('regex failed')

    return match_obj

def generate_output(template, template_dict, max_width):
    '''
    Generates the output from the given template and its dict.

    @param max_width Maximum width of all lines in the output. Values <= 0 are
        ignored, so python's default will be used instead.
    @throws GenerateOutputError
    @param template String the output template with placeholders (or not) to replace
    with their proper values.
    @param template_dict Dictionary Dictionary of template-placeholder value to use with
    formatting the template.
    @return the output string
    @date Feb 12, 2011
    @author Matthew Todd
    '''
    try:
        out_template = get_template(options.template_file, options.base_dir)

        if max_width > 0:
            return textwrap.fill(out_template.format(**template_dict), width=max_width)
        else:
            return out_template.format(**template_dict)
    except KeyError as e:
        raise GenerateOutputError('unknown identifier/placeholder: %s' % e)

def create_template_dict(match_obj, time_format):
    '''
    Create the template dict to be used to substitute in real values.

    @param match_obj the regex match object from "sudo apt-get upgrade ...".
        Contains the data to use to fill the dict.
    @param time_format a format string to be used in formatting the time
        placeholder. Should be of the format as described by the Python spec
        (probably same or very similar to C spec as well.)
    @return dictionary with the template placeholder's as keys and their
        apporopriate values (from match_obj)
    @param match_obj regex-match-obj the regex match object from "sudo apt-get upgrade ...". Contains the data to use
        to fill the dict.
    @return dictionary with the template placeholder's as keys and their apporopriate values (from match_obj)
    @date Feb 11, 2011
    @author Matthew Todd
    '''
    upgrade = match_obj.group(1)
    install = match_obj.group(2)
    remove = match_obj.group(3)
    not_upgraded = match_obj.group(4)
    cur_time = time.strftime(time_format)
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

    Has a default catch all except clause which logs the exception. Normally
    catch-alls are undesired b/c it may hide/obscure problems, but b/c this
    program is likely to be run as a cron job, we need a way to catch
    exceptions/errors/etc for later debugging/assesing/etc.

    @return The exit code. The meaning of the exit code is store above near the
    top of the file in the ERROR_CODES dictionary.

    @date Feb 11, 2011
    @author Matthew Todd
    '''
    out_file = compute_out_file(options.base_dir, args[0])
    log.info("out_file = '%s'" % out_file)

    try:
        if options.network_check:
            check_network()

        call_update(options.num_update_checks, options.sleep_period)

        upgrade_output = get_upgrade_output()

        match_obj = parse_upgrade_output(upgrade_output)

        template_dict = create_template_dict(match_obj, options.time_format)

        template = get_template(options.template_file, options.base_dir)

        output = generate_output(template, template_dict, options.max_width)

        write_msg(out_file, output, is_error=False)

        log.info('normal exit: %s' % time.asctime())
        return NO_ERROR

    except CustomException as e:
        log.exception(e)
        write_msg(out_file, ERROR_MSGS[e.key], is_error=True)
        return ERROR_CODES[e.key]

    except Exception as e:
        log.exception(e)
        write_msg(out_file, ERROR_MSGS['default'], is_error=True)
        return ERROR_CODES['default']

if __name__ == "__main__":
    sys.exit(main())
