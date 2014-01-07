import threading, logging, os


class ControlThread(threading.Thread):
    """ This Thread opens controlfifo for reading and translates commands into
        method-invocations. """
    def start_controller(self, oyster_inst, cfile):
        """ sets oyster-instance and starts the Thread. Use this method for
            starting the Thread. """
        self.oyster = oyster_inst
        self.controlfile = cfile
        self.log = logging.getLogger("oyster")
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

        self.log.debug("command: " + command)

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