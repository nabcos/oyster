#!/usr/bin/python
# -*- coding: ISO-8859-1 -*
# oyster - a perl-based jukebox and web-frontend
#
# Copyright (C) 2004 Benjamin Hanzelmann <ben@nabcos.de>,
#  Stephan Windm�ller <windy@white-hawk.de>,
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

import cgi
import config
import taginfo
import fifocontrol
import cgitb
import sys
import os.path
import urllib
import common
import re
cgitb.enable()

myconfig = config.get_config('oyster.conf')
basedir = myconfig['basedir']
mediadir = myconfig['mediadir'][:-1]
form = cgi.FieldStorage()

playlist = config.get_playlist()

common.navigation_header()

try:
    soundfile = form['file'].value
except KeyError:
    soundfile = ''

if form.has_key('action'):
    fifocontrol.do_action(form['action'].value, soundfile)

if not os.path.exists(mediadir + soundfile):
    print "<h1>Error!</h1>"
    print "<p>File <strong>" + soundfile + "</strong> could not be found.</p>"
    print "</body></html>"
    sys.exit()

if os.path.exists(myconfig['basedir']):
    oysterruns = 1
else:
    oysterruns = 0

print "<p>Info for "

subdir = soundfile.replace(mediadir,'',1)
subdir = os.path.dirname(subdir)
soundfileonly = os.path.basename(soundfile)
dirs = subdir.split('/')
incdir = ''
for partdir in dirs:
    escapeddir = urllib.quote(incdir + partdir)
    print "<a href='browse.py?dir=" + escapeddir +"'>" + partdir + "</a> / "
    incdir = incdir + partdir + "/"

print cgi.escape(soundfileonly) + "</p><br clear='all'>"

isblacklisted = 0
blacklist = open (myconfig['savedir'] + "blacklists/" + playlist)
for rule in blacklist.readlines():
    if soundfile == rule[:-1]:
        isblacklisted = 1
blacklist.close()

escapedfile = urllib.quote(soundfile)

print "<table width='100%'><tr>"
if oysterruns:
    print "<td align='left'><span class='file'><a class='file' href='oyster-gui.py?" + \
        "vote=" + escapedfile + "' target='curplay'>Vote</a> / " + \
        "<a class='file' href='oyster-gui.py?action=enqueue&amp;file=" + escapedfile + \
        "' target='curplay'>Enqueue</a> this song</span></td>"
else:
    print "<td></td>"

regexfile = cgi.escape("^" + soundfile + "$")

if isblacklisted:
    print "<td align='right'><span class='blacklisted'>File is blacklisted</span></td></tr></table>"
else:
    print "<td align='right'><a class='file' href='blacklist.py?" + \
        "affects=" + regexfile + "&amp;action=add'>Add this song to Blacklist</a></td></tr></table>"

tag = taginfo.get_tag(mediadir + soundfile)

timesplayed = 0
logmatcher = re.compile('\A[0-9]{4}[0-9]{2}[0-9]{2}\-[0-9]{2}[0-9]{2}[0-9]{2}\ ([^\ ]*)\ (.*)\Z')
log = open (myconfig['savedir'] + "logs/" + playlist)
for line in log.readlines():
    matcher = logmatcher.match(line[:-1])
    if matcher != None and matcher.group(2).find(soundfile) > -1 and matcher.group(1) == 'DONE':
        timesplayed = timesplayed + 1

log.close()

albumdir = os.path.dirname(mediadir + soundfile)
coverdata = common.get_cover(albumdir, myconfig['coverwidth'])

print "<table border='0' width='100%'>"
if tag.has_key('title'):
    print "<tr><td class='fileinfo'><strong>Title</strong></td><td>" + tag['title'] + \
        "</td><td rowspan='6' class='fileinfoimage' width='120'>" + coverdata + "</td></tr>"
else:
    print "<tr><td class='fileinfo'></td><td rowspan='6'>$coverdata</td></tr>"

if tag.has_key('artist'):
    print "<tr><td class='fileinfo'><strong>Artist</strong></td><td>"
    print "<a href='search.py?searchtype=normal&playlist=current&search=" + \
        tag['artist'] + "' title='Search for this artist'>" + tag['artist'] + "</a>"
    print "</td></tr>"

tagtuple = (
    ('Album', 'album'),
    ('Track Number', 'track'),
    ('Year', 'year'),
    ('Genre', 'genre'),
    ('Comment', 'comment'),
    ('File Format', 'format'),
    ('Playtime', 'playtime')
)

for line in tagtuple:
    if tag.has_key(line[1]):
        print "<tr><td class='fileinfo'><strong>" + line[0] + "</strong></td>" + \
            "<td>" + tag[line[1]] + "</td></tr>"

print "<tr><td colspan='2'>&nbsp;</td></tr>"
print "<tr><td class='fileinfo'><strong>Times played</strong></td><td>" + str(timesplayed) + "</td></tr>"
print "<tr><td class='fileinfo'><strong>Current Oyster-Score</strong></td>"
print "<td><a href='fileinfo.py?action=scoredown&amp;file=" + escapedfile + "' title='Score down'>"
print "<img src='themes/" + myconfig['theme'] + "/scoredownfile.png' border='0' alt='-'></a> "
print "<strong>" + str(tag['score']) + "</strong>"
print " <a href='fileinfo.py?action=scoreup&amp;file=" + escapedfile + "' title='Score up'>"
print "<img src='themes/" + myconfig['theme'] + "/scoreupfile.png' border='0' alt='+'></a></td></tr>"
print "</table>"

print "</body></html>"