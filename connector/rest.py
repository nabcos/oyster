import connector

__author__ = 'hanzelm'

import flask
import threading

app = flask.Flask(__name__)
cmd = '/cmd/'

class RestController(threading.Thread):

    def __init__(self, oyster):
        super(RestController, self).__init__()

        connector.rest.oyster = oyster
        # app.config['DEBUG'] = True


    def run(self):
        app.run()

    def stop(self):
        pass

@app.route(cmd + 'next')
def next():
    connector.rest.oyster.next()
    return connector.rest.oyster.nextfilestoplay[0]

@app.route("/")
def hello():
    return "Hello World!"
