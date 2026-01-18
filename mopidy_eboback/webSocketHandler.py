import json

import tornado.websocket
import logging

logger = logging.getLogger(__name__)
active_clients = set() #todo: make class variable.


def broadcast(message):
    for client in active_clients:
        client.ioloop.add_callback(WebsocketHandler.write_message, client, message)

class WebsocketHandler(tornado.websocket.WebSocketHandler):

    def initialize(self, config):
        logger.info("eboplayer websocket initializedxxx")
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
            logger.info("eboplayer websocket start_scan received")
            the_event = {
                "event" : "scan_started",
                "some_data" : "nada..."
            }
            broadcast(json.dumps(the_event))

    def on_close(self):
        active_clients.remove(self)

