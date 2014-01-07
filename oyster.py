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

import os
import sys
import logging
import logging.config
import random
import threading
import time
import signal
import re
import oysterconfig
import datetime

__version__ = 2
__revision__ = 1


class Oyster:
    """ By creating an instance of this class the configfile is read and
        initialized.  Use play(oyster_instance.filetoplay) to start playing."""

    # the config file needs to be in pwd
    configfile = os.getcwd() + "/config/default"
    config = {}
    confdir = ""

    # lists of filenames with full path
    filelist = []
    history = []
    scorelist = []

    # list of lists: [ filename, no. of votes, reason (VOTED|ENQUEUED) ]
    votelist = []

    scorepointer = 0
    scoresfile = ""
    scoressize = "100"

    savedir = "/var/www/oyster"
    basedir = "/tmp/oyster"
    listdir = ""
    mediadir = "/"
    blacklistdir = ""
    logdir = ""
    scoresdir = ""

    votefile = ""
    votepercentage = 20
    favmode = False

    playlist = "default"
    playlist_changed = ""

    controlfile = ""
    controlfilemode = 0600

    filetypes = {"mp3": "/usr/bin/mpg123", "ogg": "/usr/bin/ogg123"}
    filetoplay = ""
    current_playreason = ""

    nextfilestoplay = []
    len_nextfiles = 5

    # pid of musicplayer     
    playerid = 0

    # state variables 
    do_exit = False
    paused = False
    mode = "vote"
    do_not_switch = False

    playreasons = []
    nextreason = ""

    vol_regex = None

    # open fd for reading commands 
    control = None

    def __init__(self):
        """ initialise configuration and build filelist """
        log.debug("start init")

        self.init_config()

        # setup basedir
        if not os.access(self.basedir, os.F_OK):
            log.debug("setup basedir")
            os.makedirs(self.basedir)
        else:
            log.debug("removing old basedir")
            for root, dirs, files in os.walk(self.basedir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
            os.rmdir(self.basedir)
            os.makedirs(self.basedir)
        
        self.__setup_savedir()
        self.__check_access()
        if __name__ == '__main__':
            # redirect stdout/stderr - silence!
            outfile = os.open(self.basedir + "/oyster.stdout", os.O_RDWR|os.O_CREAT|os.O_TRUNC)
            errfile = os.open(self.basedir + "/oyster.stderr", os.O_RDWR|os.O_CREAT|os.O_TRUNC)
            os.dup2(outfile, 1)
            os.dup2(errfile, 2)

        # write current pid
        log.debug("writing pid")
        pidfile = open(self.basedir + "/pid", 'w')
        pidfile.write(str(os.getpid()) + "\n")
        pidfile.close()

        # write name of current playlist (in init -> default)
        self.__write_playlist_status()

        # read old default-playlist (list of all files in mediadir)
        # (one song is played from there while we build the new list) 
        log.debug("reading old default list")
        for i in range(0, self.len_nextfiles):
            self.playreasons.append("filler")
        self.load_playlist("default")

        # read scores for playlist 
        self.__update_scores()

        # initialize random
        random.seed()

        # make fifos
        log.debug("make fifos")
        os.mkfifo(self.controlfile)
        os.chmod(self.controlfile, self.controlfilemode)

        # init votefile
        vfile = open(self.basedir + "/votes", 'w')
        vfile.write("")
        vfile.close()

        # favmod is off at start
        self.__write_favmode("off")

        self.write_volume()
        
        self.control = open(self.controlfile, 'r+')

        plhelper = PlaylistBuilder()
        plhelper.build_playlist(self)

        # for basedir/status -> playing
        self.unpause()

        log.debug("end init")

    def __setup_savedir(self):
        """ creates the directories necessary for saving persistent data (logs,
            playlists, ...) """
        log.debug("setup savedir")
        if not os.access(self.savedir, os.F_OK):
            os.makedirs(self.savedir)
        if not os.access(self.listdir, os.F_OK):
            os.makedirs(self.listdir)
        if not os.access(self.blacklistdir, os.F_OK):
            os.makedirs(self.blacklistdir)
        if not os.access(self.scoresdir, os.F_OK):
            os.makedirs(self.scoresdir)    
        if not os.access(self.logdir, os.F_OK):
            os.makedirs(self.logdir)
        if not os.access(self.confdir, os.F_OK):
            os.makedirs(self.confdir)
            
    def __check_access(self):
        """ checks if oyster can access the directories r/w """
        log.debug("checking access-rights")
        for i in [self.savedir, self.listdir, self.blacklistdir, self.scoresdir, self.logdir, self.confdir]:
            if not os.access(i, os.R_OK | os.W_OK):
                log.debug("no r/w-access to all savedir-directories!")
                print "no r/w-access to all savedir-directories!"
                print "exiting..."
                sys.exit(1)

    def __write_favmode(self, status):
        """ writes string argument status to basedir/favmode """
        favfile = open(self.basedir + "/favmode", 'w')
        favfile.write(status + "\n")
        favfile.close()

    def write_volume(self):
        """ write volume percentage to basedir/volume """
        volfile = open(self.basedir + "/volume", 'w')
        volume = self.get_volume()
        volfile.write(volume + "\n")
        volfile.close()

    def get_volume(self):
        vol = os.popen(self.config['vol_get_cmd'])
        if self.vol_regex is None:
            self.vol_regex = re.compile(self.config['vol_filter_regexp'])

        for line in vol:
            match = self.vol_regex.search(line)
            if match is not None:
                vol.close()
                return match.group(1)

        vol.close()
        return "-1"

    def __write_playlist_status(self):
        """ writes name of current playlist to basedir/playlist """
        log.debug("writing playlist")
        plfile = open(self.basedir + "/playlist", 'w')
        plfile.write(self.playlist + "\n")
        plfile.close()

    def __update_scores(self):
        """ checks for scorefile and reinitialises the scorelist """
        log.debug("updating scores")
        if os.access(self.scoresfile, os.R_OK):
            sfile = open(self.scoresfile, 'r')
            self.scorepointer = int(sfile.readline().rstrip())
            self.scorelist = []
            for line in sfile.readlines():
                self.scorelist.append(line.rstrip())
            sfile.close()
        else:
            # no scorefile -> empty list 
            self.scorepointer = 0
            self.scorelist = []
        # FIXME cut off entries after scoressize has changed!

    def __write_scores(self):
        """ writes the scorelist to savedir/scores/$playlist """
        # save scores
        sfile = open(self.scoresfile, 'w')
        # first line is pointer to the last inserted line
        # (RRD-style DB) 
        sfile.write(str(self.scorepointer) + "\n")
        for line in self.scorelist:
            sfile.write(line + "\n")
        sfile.close()

    def __write_history(self):
        """ writes the history of played files to basedir/history """
        hfile = open(self.basedir + "/history", 'w')
        for entry in self.history:
            hfile.write(entry + "\n")
        hfile.close()
    
    def __test_blacklist(self, name):
        """ check whether argument name is in the blacklist for the current
            playlist and returns boolean value """
        if os.access(self.blacklistdir + "/" + self.playlist, os.R_OK):
            bfile = open(self.blacklistdir + "/" + self.playlist, 'r')
            for line in bfile.readlines():
                if re.compile(line.rstrip()).search(name) is not None:
                    return True
                if line.startswith('^'):
                    if re.compile(line.replace('^', "^" + self.mediadir).rstrip()).search(name) is not None:
                        return True
        return False

    def __choose_file(self):
        """ chooses file from either filelist or scores and tests for blacklist
        """
        log.debug("choose file from list")
        if len(self.scorelist) != 0:
            # test if we play from scores or normal playlist
            #randi = random.randint(0, 100)
            scoreprobability = self.votepercentage

            if self.favmode:
                scoreprobability = 100

            if random.randint(0, 100) < scoreprobability:
                playreason = "SCORED"
                return random.choice(self.scorelist), playreason
        chosen = random.choice(self.filelist)
        if self.__test_blacklist(chosen):
            self.__playlog(self.__gettime() + " BLACKLIST " + chosen)
            try:
                return self.__choose_file()
            except RuntimeError:
                log.debug("recursion error! too many matches from blacklist!")
                playreason = "BLACKLISTFORCED"
                return chosen, playreason
        playreason = "PLAYLIST"
        return chosen, playreason

    def __write_votelist(self):
        log.debug("writing votelist")
        if self.mode == "vote":
            #self.votelist.sort(self.__votelist_sort)
            if len(self.votelist) != 0:
                vfile = open(self.basedir + "/votes", 'w')
                for entry in self.votelist:
                    vfile.write(entry[0] + "," + str(entry[1]) + "\n")
                vfile.close()
            else:
                vfile = open(self.basedir + "/votes", 'w')
                vfile.write("")
                vfile.close()
                
    @staticmethod
    def __gettime():
        """ returns time in "%Y%m%d-%H%M"-format """
        dateinst = datetime.datetime(1, 2, 3)
        return dateinst.today().strftime("%Y%m%d-%H%M%S")

    def __done(self):
        """ this method is invoked when the musicplayer quits.
            It writes the appropriate log entry and plays the next file. """
        log.debug("done playing")
        # if doExit is set don't play again 
        if not self.do_exit:
            # first song is always empty -> no log entry 
            if self.filetoplay != "":
                self.__playlog(self.__gettime() + " " + self.nextreason + " " +
                               self.filetoplay)

            if len(self.votelist) != 0:
                # there are votes that have not been played:
                # play first file (has most votes)
                self.filetoplay = self.votelist[0][0]
                self.current_playreason = self.votelist[0][2]
                self.__playlog(self.__gettime() + " " + self.current_playreason +
                               " " + self.filetoplay)
                self.votelist = self.votelist[1:]
                self.__write_votelist()

            # do_not_switch may be set when play_previous is used
            # in this case, the file is already set -> do nothing 
            elif not self.do_not_switch:
                # normal operation: play next file and choose another one 
                self.filetoplay = self.nextfilestoplay[0]
                self.nextfilestoplay = self.nextfilestoplay[1:]
                self.nextfilestoplay.append("filler")
                self.current_playreason = self.playreasons[0]
                self.__playlog(self.__gettime() + " " + self.current_playreason + " " +
                               self.filetoplay)
                self.playreasons = self.playreasons[1:]
                self.playreasons.append("filler")
                self.choose_file(self.len_nextfiles-1)
                self.hist_pointer = len(self.history)

            # reset state
            self.do_not_switch = False
            # nextreason can be "SKIPPED"
            self.nextreason = "DONE"

            # wait for sound buffer to get empty (ogg123 exits early) 
            time.sleep(2)
            # self.play(self.filetoplay)
 
    def __playlog(self, string):
        """ writes the argument string to the right logfile
            (savedir/logs/$playlist) """
        if self.playlist_changed != "":
            # after a playlist change, DONE/SKIPPED should go into the old
            # logfile 
            plist = self.playlist_changed
            self.playlist_changed = ""
        else:
            plist = self.playlist
        plfile = open(self.savedir + "/logs/" + plist, 'a')
        plfile.write(string + "\n")
        plfile.close()

    @staticmethod
    def get_defaults():
        defaults = {"savedir": "/var/www/oyster",
                    "basedir": "/tmp/oyster",
                    "mediadir": "/",
                    "voteplay": "10",
                    "filetypes": "mp3,ogg",
                    "mp3": "/usr/bin/mpg123",
                    "ogg": "/usr/bin/ogg123",
                    "len_nextfiles": "5",
                    "skip_deletes": "False",
                    "control_mode": "0600",
                    "maxscored": "30"
                    }
        return defaults

    def init_config(self, configfile=os.getcwd()+"/config/default", configdict=None):
        """ read config and set attributes """

        if configdict is None:
            # get config and get values into "real" variables
            if os.access(configfile, os.R_OK):
                self.config = oysterconfig.getConfig(configfile)
            else:
                self.config = self.get_defaults()
        else:
            self.config = configdict

        # for __test_blacklist - stop recursing after 200 hits from the
        # blacklist
        sys.setrecursionlimit(200)

        evalconfig = {"savedir": 'self.savedir = self.config["savedir"].rstrip("/")',
                      "mediadir": 'self.mediadir = self.config["mediadir"].rstrip("/")',
                      "basedir": 'self.basedir = self.config["basedir"].rstrip("/")',
                      "voteplay": 'self.votepercentage = int(self.config["voteplay"].rstrip("/"))',
                      "maxscored": 'self.scoressize = int(self.config["maxscored"])',
                      "control_mode": 'self.controlfilemode = int(self.config["control_mode"], 8)',
                      "filetypes": 'for ftype in self.config["filetypes"].split(","):' +
                                   ' self.filetypes[ftype] = self.config[ftype]',
                      "len_nextfiles": 'self.len_nextfiles = int(self.config["len_nextfiles"])'
                      }
        
        for key in self.config.keys():
            try:
                exec evalconfig[key]
            except KeyError:
                pass

        self.listdir = self.savedir + "/lists"
        self.scoresfile = self.savedir + "/scores/" + self.playlist
        self.scoresdir = self.savedir + "/scores"
        self.blacklistdir = self.savedir + "/blacklists"
        self.logdir = self.savedir + "/logs"

        self.votefile = self.basedir + "/votes"
        self.controlfile = self.basedir + "/control"

        self.confdir = self.savedir + "/config"

    def choose_file(self, filepos, delete=False):
        """ chooses one of the next files to play from either filelist or
        scores and writes it to basedir/nextfile """

        log.debug("choose next file " + str(filepos) + " to play")
        try:
            if delete:
                del self.nextfilestoplay[filepos]
                (entry, reason) = self.__choose_file()
                self.nextfilestoplay.append(entry)
                self.playreasons.append(reason)
            else:
                (self.nextfilestoplay[filepos], self.playreasons[filepos]) = self.__choose_file()
        except IndexError:
            # TODO log!
            pass
        nfile = open(self.basedir + "/nextfile", 'w')
        for filename in self.nextfilestoplay:
            nfile.write(filename + "\n")
        nfile.close()

    def build_playlist(self, mdir):
        """ builds the default playlist with argument mdir as root """
        log.debug("building playlist")
        flist = []

        # append every file with extension in filetypes to filelist 
        for root, dirs, files in os.walk(mdir, topdown=False):
            for name in files:
                if name[name.rfind(".")+1:] in self.filetypes.keys():
                    flist.append(os.path.join(root, name).rstrip())

        lfile = open(self.listdir + "/default", 'w')
        for line in flist:
            lfile.write(line + "\n")
        lfile.close()

        # if the playlist is not changed to another playlist than "default",
        # replace filelist in memory 
        if self.playlist == "default":
            self.filelist = flist

    def exit(self):
        """ cleanup basedir, write scores and kill player """
        log.debug("exiting oyster")

        self.do_exit = True
        
        for root, dirs, files in os.walk(self.basedir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(self.basedir)

        self.__write_scores()

        if self.playerid != 0:
            try:
                os.kill(self.playerid, signal.SIGCONT)
                os.kill(self.playerid, signal.SIGTERM)
            except OSError:
                pass

        self.__playlog(self.__gettime() + " QUIT " + self.filetoplay)
        sys.exit()

    def play(self, filestring, playreason):
        """ play file """
        if self.filetoplay != "":
            suffixpos = filestring.rfind(".")
            player = self.filetypes[filestring[suffixpos+1:]]
            self.history.append(filestring)
            self.__write_history()
            log.debug(player + " " + filestring)
            pfile = open(self.basedir + "/info", 'w')
            pfile.write(playreason + " " + filestring + "\n")
            pfile.close()
            self.playerid = os.spawnl(os.P_NOWAIT, player, player, filestring)
            os.waitpid(self.playerid, 0)
        self.__done()

    def play_previous(self):
        """ play previous file from history """
        if self.hist_pointer > 0:
            self.hist_pointer -= 1
            self.filetoplay = self.history[self.hist_pointer]
            self.do_not_switch = True
            self.next()

    def next(self):
        """ skip the playing file """
        self.nextreason = "SKIPPED"
        if self.playerid != 0:
            try:
                os.kill(self.playerid, signal.SIGTERM)
            except OSError:
                pass

    def pause(self):
        """ pause playing """
        self.paused = True
        pfile = open(self.basedir + "/status", 'w')
        pfile.write("paused")
        pfile.close()
        if self.playerid != 0:
            try:
                os.kill(self.playerid, signal.SIGSTOP)
            except OSError:
                pass

    def unpause(self):
        """ resume playing """
        self.paused = False
        pfile = open(self.basedir + "/status", 'w')
        pfile.write("playing")
        pfile.close()
        if self.playerid != 0:
            try:
                os.kill(self.playerid, signal.SIGCONT)
            except OSError:
                pass

    def enable_favmode(self):
        """ enable favmode (play only from scores) """
        self.favmode = True
        self.nextfilestoplay = []
        self.fill_next_files_to_play()
        self.__write_favmode("on")

    def disable_favmode(self):
        """ disable favmode (normal playing) """
        self.favmode = False
        self.nextfilestoplay = []
        self.fill_next_files_to_play()
        self.__write_favmode("off")

    def enqueue(self, filestring, reason):
        """ queue file for playing with $reason as logentry """
        if self.mode == "vote":
            found = None
            foundpos = -1
            self.votelist.reverse()
            for i in range(len(self.votelist)):
                if self.votelist[i][0] == filestring:
                    self.votelist[i][1] += 1
                    found = self.votelist[i]
                    foundpos = i
                if found is not None:
                    if self.votelist[i][1] >= found[1] and self.votelist[i][0] != found[0]:
                        self.votelist = self.votelist[:i] + [found] + self.votelist[i:]
                        del self.votelist[foundpos]
                        self.votelist.reverse()
                        self.__write_votelist()
                        return None
                    elif i == len(self.votelist)-1:
                        self.votelist.append(found)
                        del self.votelist[foundpos]
                        self.votelist.reverse()
                        self.__write_votelist()
                        return None
            self.votelist.reverse()
            self.votelist.append([filestring, 1, reason])
            self.__write_votelist()

    def vote(self, filestring, reason):
        """ queue file for playing and raise score """
        if self.mode == "vote":
            self.enqueue(filestring, reason)
            self.scoreup(filestring)

    def scoreup(self, filestring):
        """ raise score for file """
        log.debug("scoreup")
        self.scorepointer += 1
        if self.scorepointer == self.scoressize:
            self.scorepointer = 0
        self.scorelist.append(filestring)
        self.__write_scores()

    def scoredown(self, filestring):
        """ lower score for file """
        try:
            self.scorelist.remove(filestring)
            self.scorepointer -= 1
            if self.scorepointer < 0:
                self.scorepointer = 0
            self.__write_scores()
        except ValueError:
            # when file is not in the scorelist this Error will be raised 
            pass

    def dequeue(self, filestring):
        """ remove file from the queue of files to play.  Returns the entry
            from the votelist (a triple: filename, number of votes, reason) """
        for tup in self.votelist:
            if filestring == tup[0]:
                self.votelist.remove(tup)
                return tup
        return None

    def unvote(self, filestring):
        """ remove file from the queue of files to play. If the score was
            raised before, lower it. """
        tup = self.dequeue(filestring)
        if tup is not None:
            if tup[2] == "VOTED":
                for i in range(1, tup[1]):
                    self.scoredown(filestring)
        self.__write_votelist()

    def enqueue_list(self, filestring):
        """ Open xmms-style playlist and enqueue the files in it. """
        try:
            lfile = open(filestring, 'r')
        except IOError:
            return
        listpath = filestring[:filestring.rfind("/")]
        for line in lfile.readlines():
            pos_hash = line.find('#')
            # forget comments (hash with only spaces before) 
            if (pos_hash != -1) and (line[:pos_hash] == " "*(pos_hash+1)):
                continue
            pos_slash = line.find("/")
            if pos_slash == 0:
                # path is absolute 
                self.enqueue(line.rstrip(), "ENQUEUED")
            else:
                # path is relative 
                self.enqueue(listpath + "/" + line.rstrip(), "ENQUEUED")

    def build_regexp_list(self, regexp):
        deflist = open(self.listdir + "/default", 'r')
        deflines = deflist.readlines()
        try:
            ret = []
            matcher = re.compile(regexp)
            for line in deflines:
                line = line.replace(self.mediadir, '', 1)
                if matcher.match(line.rstrip()):
                    ret.append(self.mediadir + line)
            if len(ret) == 0:
                log.debug("regexplist: no matches")
                return deflines
            return ret
        except:
            log.debug("regexplist: exception")
            return deflines

    def fill_next_files_to_play(self):
        for i in range(0, self.len_nextfiles):
            self.nextfilestoplay.append("filler")
            self.choose_file(i)

    def load_playlist(self, listname, skip=True, checkskip=False):
        """ load oyster-playlist (discard list in memory) """
        # do we need to skip the next random songs?
        if checkskip:
            if not self.filelist:
                skip = True
            else:
                skip = False

        if os.access(self.listdir + "/" + listname, os.R_OK):
            # load config for this list or reload default
            if os.access(self.confdir + "/" + listname, os.R_OK):
                self.init_config(configfile=self.confdir + "/default")
                self.init_config(configfile=self.confdir + "/" + listname)
            elif os.access(self.confdir + "/default", os.R_OK):
                self.init_config(configfile=self.confdir + "/default")
            else:
                self.init_config(configdict=self.get_defaults())

            deflist = open(self.listdir + "/" + listname, 'r')
            self.filelist = []
            self.playlist_changed = self.playlist
            self.playlist = listname
            self.scoresfile = self.savedir + "/scores/" + self.playlist
            self.__update_scores()
            self.__write_playlist_status()

            if self.favmode:
                self.disable_favmode()

            lines = deflist.readlines()
            if lines[0].startswith("^"):
                log.debug("regex list")
                ret = self.build_regexp_list(lines[0].rstrip())
                lines = ret
            for line in lines:
                self.filelist.append(line.rstrip())
            self.nextfilestoplay = []
            if skip:
                self.fill_next_files_to_play()

    def shift(self, amount, pos):
        """ shift the votelist entry on position /pos/ by /amount/ (positive values shift up) """
        if amount > 0:
            if pos-amount <= 0:
                self.votelist = [self.votelist[pos]] + self.votelist
                del self.votelist[pos+1]
            else:
                self.votelist = self.votelist[:pos-amount] + [self.votelist[pos]] + self.votelist[pos-amount:]
                del self.votelist[pos+1]
        elif amount < 0:
            if pos-amount >= len(self.votelist)-1:
                self.votelist = self.votelist + [self.votelist[pos]]
                del self.votelist[pos]
            else:
                self.votelist = self.votelist[:pos-amount+1] + [self.votelist[pos]] + self.votelist[pos-amount+1:]
                del self.votelist[pos]
        self.__write_votelist()
            

class ControlThread(threading.Thread):
    """ This Thread opens controlfifo for reading and translates commands into
        method-invocations. """
    def start_controller(self, oyster_inst, cfile):
        """ sets oyster-instance and starts the Thread. Use this method for
            starting the Thread. """
        self.oyster = oyster_inst
        self.controlfile = cfile
        self.start()

    def run(self):
        while 1:
            self.read_control()

    def read_control(self):
        commandline = self.controlfile.readline().rstrip()
        cpos = commandline.find(" ")
        if cpos == -1:
            command = commandline
        else:
            command = commandline[:cpos]

        log.debug("command: " + command)

        if command == "NEXT":
            self.oyster.next()
        elif command == "CHANGERANDOM":
            # arg in [0:inf]
            try:
                arg = int(commandline[cpos+1:])
                self.oyster.choose_file(arg)
            except ValueError:
                print "ValueError! Oh mein Gott!"
                print "x" + commandline[cpos+1:] + "x"
                pass
        elif command == "DELRANDOM":
            # arg in [0:inf]
            try:
                arg = int(commandline[cpos+1:])
                self.oyster.choose_file(arg, delete=True)
            except ValueError:
                pass
        elif command == "QUIT":
            self.oyster.exit()
        elif command == "PAUSE":
            if not self.oyster.paused:
                self.oyster.pause()
            else:
                self.oyster.unpause()
        elif command == "UNPAUSE":
            self.oyster.unpause()
        elif command == "PREV":
            self.oyster.play_previous()
        elif command == "VOTE":
            self.oyster.vote(commandline[cpos+1:], "VOTED")
        elif command == "ENQUEUE":
            self.oyster.enqueue(commandline[cpos+1:], "ENQUEUED")
        elif command == "DEQUEUE":
            self.oyster.dequeue(commandline[cpos+1:])
        elif command == "UNVOTE":
            self.oyster.unvote(commandline[cpos+1:])
        elif command == "SCORE":
            if commandline[cpos+1:cpos+2] == "+":
                self.oyster.scoreup(commandline[cpos+3:])
            elif commandline[cpos+1:cpos+2] == "-":
                self.oyster.scoredown(commandline[cpos+3:])
        elif command == "ENQLIST":
            self.oyster.enqueue_list(commandline[cpos+1:])
        elif command == "RELOADCONFIG":
            self.oyster.init_config()
        elif command == "FAVMODE":
            self.oyster.enable_favmode()
        elif command == "NOFAVMODE":
            self.oyster.disable_favmode()
        elif command == "LOAD":
            self.oyster.load_playlist(commandline[cpos+1:])
        elif command == "SHIFTUP":
            try:
                arg = int(commandline[cpos+1:])
                self.oyster.shift(1, arg)
            except ValueError:
                print "ValueError! " + commandline[cpos+1:]
        elif command == "SHIFTDOWN":
            try:
                arg = int(commandline[cpos+1:])
                self.oyster.shift(-1, arg)
            except ValueError:
                print "ValueError! " + commandline[cpos+1:]
        elif command == "VOLDOWN":
            os.system(self.oyster.config['vol_down_cmd'])
            self.oyster.write_volume()
        elif command == "VOLUP":
            os.system(self.oyster.config['vol_up_cmd'])
            self.oyster.write_volume()
        elif command == "VOLSET":
            os.system(self.oyster.config['vol_set_cmd'] + " " + commandline[cpos+1:] + "%")
            self.oyster.write_volume()

        
class PlaylistBuilder(threading.Thread):
    """ asynchronus default playlist building. Wonderful. """
    oyster = None

    def build_playlist(self, oyster_inst):
        self.oyster = oyster_inst 
        self.start()

    def run(self):
        self.oyster.build_playlist(self.oyster.mediadir)

if os.path.exists("oysterlog.conf"):
    logging.config.fileConfig("oysterlog.conf")

log = logging.getLogger("oyster")

if __name__ == '__main__':
    oy = Oyster()

    cthread = ControlThread()
    cthread.setDaemon(True)
    cthread.start_controller(oy, oy.control)

    # if we have nothing to play, wait until first default playlist is built
    if len(oy.filelist) == 0:
        while len(oy.filelist) == 0:
            pass
        oy.loadPlaylist("default", skip=True)

    while not oy.do_exit:
        oy.play(oy.filetoplay)
