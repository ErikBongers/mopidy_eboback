import json
import pathlib

import tornado.websocket
import logging

from mopidy_eboback.commands import ScanCommand, UpdateMetaCommand
from mopidy_eboback.meta_scanner.scanner import Scanner, ProgressReporter

logger = logging.getLogger(__name__)
active_clients = set() #todo: make class variable.


def broadcast(message):
    for client in active_clients:
        client.ioloop.add_callback(WebsocketHandler.write_message, client, message)

class WebsocketHandler(tornado.websocket.WebSocketHandler):

    def initialize(self, config):
        logger.info("eboplayer websocket initialized")
        self.config = config
        self.ioloop = tornado.ioloop.IOLoop.current()

    def check_origin(self, origin):
        return True #allows cross-domain requests

    def open(self):
        active_clients.add(self)

    def on_message(self, message):
        logger.info("eboplayer websocket message received: " + message)
        obj = json.loads(message)
        if obj["method"] == "start_scan":
            self.scan()
            return

    def on_close(self):
        active_clients.remove(self)

    def scan(self):
        from threading import Thread
        logger.info("eboplayer websocket start_scan received")
        media_dir = pathlib.Path(self.config["eboback"]["media_dir"]).resolve()
        the_event = {
            "event": "scan_started",
            "message": f"Scanning {str(media_dir)} ..."
        }
        broadcast(json.dumps(the_event))

        thread = Thread(target=threaded_scan, args=(self.config,))
        thread.start()


def threaded_scan(config):
    def report(message) -> None:
        the_event = {
            "event": "scan_status",
            "message": message
        }
        broadcast(json.dumps(the_event))

    reporter = ProgressReporter(report, report, report)
    scanner = Scanner(config, False, None, reporter)
    scanner.run()

    the_end = {
        "event": "scan_finished",
        "message": "nada..."
    }
    broadcast(json.dumps(the_end))
