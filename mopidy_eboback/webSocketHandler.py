import json
import pathlib
from typing import Literal

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
        broadcast_scan_event("scan_started", f"Scanning {str(media_dir)} ...", "progress")

        thread = Thread(target=threaded_scan, args=(self.config,))
        thread.start()

ScanStatusType = Literal["progress", "details", "error"]
ScanStatusEvent = Literal["scan_started", "scan_finished", "scan_status"]

def broadcast_scan_event(event_type: ScanStatusEvent, message: str, status_type: ScanStatusType):
    the_event = {
        "event": event_type,
        "message": message,
        "type": status_type
    }
    broadcast(json.dumps(the_event))

def threaded_scan(config):
    def progress(message) -> None:
        broadcast_scan_event("scan_status", message, "progress")
    def details(message) -> None:
        broadcast_scan_event("scan_status", message, "details")
    def error(message) -> None:
        broadcast_scan_event("scan_status", message, "error")


    reporter = ProgressReporter(progress, details, error)
    scanner = Scanner(config, False, None, reporter)
    scanner.run()
    broadcast_scan_event("scan_finished", "Scan finished.", "progress")
