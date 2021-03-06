#!/usr/bin/python
# -*- coding: UTF-8 -*-

# oyster - a python-based jukebox and web-frontend
#
# Copyright (C) 2004 Benjamin Hanzelmann <ben@nabcos.de>,
#  Stephan WindmÃ¼ller <windy@white-hawk.de>,
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

import taginfo
import urllib
import re
import cgitb
import sys
cgitb.enable()

import cgi
form = cgi.FieldStorage()

import common
common.navigation_header("Lyrics")

if form.has_key('artist') and form.has_key('song'):
    artist = form['artist'].value
    song = form['song'].value
else:
    print "<h1>Error: Artist or songtitle not specified!</h1></body></html>"
    sys.exit()

try:
    from SOAPpy import WSDL
except ImportError:
    print "<h1>Error: SOAPpy not found. Please install python-soappy to use this function.</h1>"
    print "</body></html>"
    sys.exit()

print "<h1>Lyrics for <i>" + artist + " - " + song + "</i></h1>\n"

from xml.sax import SAXParseException
from xml.parsers.expat import ExpatError

try:
    proxy = WSDL.Proxy("http://lyricwiki.org/server.php?wsdl")
    result = proxy.getSong(artist.decode("utf-8"), song.decode("utf-8"))
    lyric = result["lyrics"]

    # Try once again if failed
    if lyric == "Not found":
        import time
        time.sleep(5)
        result = proxy.getSong(artist.decode("utf-8"), song.decode("utf-8"))
        lyric = result["lyrics"]

    if lyric == "Not found":
        print "The lyrics were not found. You may " + \
            "<a href='lyrics.py?artist=" + urllib.quote(artist) + \
            "&amp;song=" + urllib.quote(song) + "'>try it again</a> " + \
            "or visit <a href='http://www.lyricwiki.org'>LyricWiki</a> yourself."
    else:
        lyric = lyric.encode("utf-8")
        url = result["url"]
        print "<pre id='lyric'>"
        print lyric
        print "</pre>"
        print "Due to licensing restrictions, only a few lines of the " \
              "<a class='file' href='" + url + "'>complete lyrics</a> are returned from LyricWiki."
except (SAXParseException, ExpatError):
    print "There was an unexpected error while communicating with the " + \
        "Webservice of LyricWiki. Please <a href='lyrics.py?artist=" + \
        urllib.quote(artist) + "&amp;song=" + urllib.quote(song) + "'>try it again</a>"

print "</body></html>"
