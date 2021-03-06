#!/usr/bin/python
# -*- coding: UTF-8 -*-

# oyster - a python-based jukebox and web-frontend
#
# Copyright (C) 2004 Benjamin Hanzelmann <ben@nabcos.de>, 
#  Stephan Windmüller <windy@white-hawk.de>, 
#  Stefan Naujokat <git@ethric.de>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

__revision__ = 1

import cgi
import config
import taginfo
import cgitb
import urllib
import re
import sys
import datetime
import os
cgitb.enable()

def whatplayed():
    start = datetime.datetime(int(form['year'].value), int(form['month'].value), int(form['day'].value), \
        int(form['hour'].value), int(form['min'].value))
    delta = datetime.timedelta(0, 0, 0, 0, int(form['range'].value))
    stop = start + delta
    start = start - delta

    rangelines = []

    def gettime(line):
    
        "Parses the given line and returns a datetime object"
        
        return datetime.datetime(int(line[0:4]), int(line[4:6]), int(line[6:8]), \
                int(line[9:11]), int(line[11:13]))


    def searchtime(begin, end):
        mid = begin + ((end - begin) / 2)
        midtime = gettime(loglines[mid])

        if end - begin < 2:
            if start < midtime:
                return begin
            else:
                return begin + 1
        
        if start < midtime:
            return searchtime(begin, mid)
        elif start > midtime:
            return searchtime(mid, end)
        else:
            return searchtime(mid, mid)

    for log in os.listdir('logs/'):

        # Read entire logfile into memory
    
        logfile = open('logs/' + log, 'r')
        loglines = logfile.readlines()
        logfile.close()

        if len(loglines) > 0 and \
            stop > gettime(loglines[0]) and start < gettime(loglines[-1]):

            counter = searchtime(0, len(loglines)-1)
            curdate = gettime(loglines[counter])

            while curdate < stop:
                rangelines.append(loglines[counter])
                counter += 1
                if counter < len(loglines):
                    curdate = gettime(loglines[counter])
                else:
                    curdate = stop

    rangelines.sort()

    print "<table>"

    logmatcher = re.compile('\A([0-9]{8}\-[0-9]{6})\ ([^\ ]*)\ (.*)\Z')
    for line in rangelines:
        matcher = logmatcher.match(line[:-1])
        playdate = matcher.group(1)
        reason = matcher.group(2)
        filename = matcher.group(3)
        if reason == 'PLAYLIST' or reason == 'VOTED' or reason == 'SCORED' or reason == 'ENQUEUED':
            displayname = taginfo.get_tag_light(filename)
            filename = filename.replace(mediadir, '', 1)
            escapedfilename = urllib.quote(filename)
            print "<tr>"
            print "<td><strong>" + playdate[9:11] + ":" + playdate[11:13] + "</strong></td>"
            print "<td><a class='file' href='fileinfo.py?file=" + escapedfilename + "'>" + displayname + "</a><br></td>"
            print "</tr>"

    print "</table>"
    
    sys.exit()

import common
common.navigation_header("History")

myconfig = config.get_config()
mediadir = myconfig['mediadir'][:-1]
form = cgi.FieldStorage()
playlist = config.get_playlist()

try:
    searchdate = datetime.datetime(int(form['year'].value), int(form['month'].value), int(form['day'].value), \
        int(form['hour'].value), int(form['min'].value))
    timerange = form['range'].value
except KeyError:
    searchdate = datetime.datetime.today()
    timerange = "20"

print "<h1>What was played?</h1>"
print "<form method='post' action='history.py' enctype='application/x-www-form-urlencoded'>"
print "<input type='hidden' name='action' value='whatplayed'/>"
print "<table>"
print "<tr><th>Time</th><td><input type='text' name='hour' size='1' value='%(hour)02d'/>:" % {"hour": searchdate.hour}
print "<input type='text' name='min' size='1' value='%(minute)02d'/></td></tr>" % {"minute": searchdate.minute}
print "<tr><th>Date</th><td><input type='text' name='day' size='1' value='%(day)02d'/>." % {"day": searchdate.day}
print "<input type='text' name='month' size='1' value='%(month)02d'/>." % {"month": searchdate.month}
print "<input type='text' name='year' size='3' value='" + str(searchdate.year) + "'/></td></tr>"
print "<tr><th>Range</th><td><input type='text' name='range' size='8' value='" + timerange + "'/> minutes</td></tr>"
print "</table>"
print "<input type='submit' value='Search'/>"
print "</form>"

if form.has_key('action') and form['action'].value == 'whatplayed':
    whatplayed()

print "</body></html>"
