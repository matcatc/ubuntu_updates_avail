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

@note: b/c script is calling apt-get, it requires root access, via sudo.

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

out_file = 'ubuntu_updates_avail.info'

try:
    # call apt-get update
    retcode = subprocess.call(["sudo", "apt-get", "update", "-qq"])

    if retcode != 0:
        with open(out_file) as f:
            f.write('update failed with %d' % retcode)
            sys.exit(retcode)


    # call and save upgrade --no-act
    retcode, output = subprocess.getstatusoutput("sudo apt-get upgrade --no-act -q")

    if retcode != 0:
        with open(out_file, 'w') as f:
            f.write('upgrade --no-act failed with %d' % retcode)
            sys.exit(retcode)

    # parse returned text
    regex = re.compile('([0-9]+) upgraded, ([0-9]+) newly installed, ([0-9]+) to remove and ([0-9]+) not upgraded.')
    match_obj = regex.search(output)

    if match_obj == None:
        with open(out_file, 'w') as f:
            f.write('regex failed')
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

    sys.exit(0)


except Exception:
    with open(out_file, 'w') as f:
        f.write("Exception occured")

    sys.exit(1)

