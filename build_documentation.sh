#!/bin/bash

# This file is part of Ubuntu Updates Avail
# Matthew A. Todd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
# File is used to build all of the documentation.
# Can be used by setup.py
# This file was copied from another one of my projects: Test Parser

echo "building doxygen documentation"
cd doc
doxygen Doxyfile

#echo "building docbook documentation"
#cd docbook
#rm *.html
#xmlto html -m config.xsl manual.dbk
