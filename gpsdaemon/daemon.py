"""
CARPI GPS DAEMON
(C) 2018, Raphael "rGunti" Guntersweiler
Licensed under MIT
"""
from logging import Logger
from time import sleep

from daemoncommons.daemon import Daemon
from daemoncommons.log import logger
from daemoncommons.errors import CarPiExitException
from redisdatabus.bus import BusWriter, TypedBusListener

from gps3 import agps3


KEY_BASE = 'carpi.gps.'


def build_key(type, name):
    global KEY_BASE
    return "{}{}{}".format(type, KEY_BASE, name)


KEY_LATITUDE = build_key(TypedBusListener.TYPE_PREFIX_FLOAT, "latitude")
KEY_LONGITUDE = build_key(TypedBusListener.TYPE_PREFIX_FLOAT, "longitude")
KEY_ALTITUDE = build_key(TypedBusListener.TYPE_PREFIX_INT, "altitude")
KEY_SPEED = build_key(TypedBusListener.TYPE_PREFIX_FLOAT, "speed")
KEY_SPEED_KMH = build_key(TypedBusListener.TYPE_PREFIX_FLOAT, "speed.kmh")
KEY_SPEED_MPH = build_key(TypedBusListener.TYPE_PREFIX_FLOAT, "speed.mph")
KEY_FIX_MODE = build_key(TypedBusListener.TYPE_PREFIX_STRING, "fixmode")
KEY_TIMESTAMP = build_key(TypedBusListener.TYPE_PREFIX_STRING, "timestamp")
KEY_CLIMB = build_key(TypedBusListener.TYPE_PREFIX_FLOAT, "climb")
KEY_TRACK = build_key(TypedBusListener.TYPE_PREFIX_FLOAT, "track")


class GpsdConnectionError(CarPiExitException):
    EXIT_CODE = 0xFA00

    def __init__(self):
        super().__init__(GpsdConnectionError.EXIT_CODE)


class GpsDaemon(Daemon):
    def __init__(self):
        super().__init__("GPS Daemon")
        self._log: Logger = None

    def _build_bus_writer(self):
        self._log.info("Connecting to Redis instance ...")
        return BusWriter(host=self._get_config('Redis', 'Host', '127.0.0.1'),
                         port=self._get_config_int('Redis', 'Port', 6379),
                         db=self._get_config_int('Redis', 'DB', 0),
                         password=self._get_config('Redis', 'Password', None))

    def startup(self):
        self._log = log = logger(self.name)
        log.info("Starting up %s ...", self.name)

        retries = 5

        bus = self._build_bus_writer()

        while True:
            sock = agps3.GPSDSocket()
            strm = agps3.DataStream()

            log.info("Connecting to GPSD...")
            sock.connect(self._get_config('GPSD', 'Host', agps3.HOST),
                         self._get_config_int('GPSD', 'Port', agps3.GPSD_PORT))
            sock.watch()

            log.info("Watching for new GPSD packages...")
            try:
                for d in sock:
                    if d:
                        strm.unpack(d)
                        bus.publish(KEY_LATITUDE, strm.lat)
                        bus.publish(KEY_LONGITUDE, strm.lon)
                        bus.publish(KEY_TIMESTAMP, strm.time)
            except OSError:
                if retries > 0:
                    log.error("Failed to fetch data from GPSD! Retrying %s more times", retries)
                    retries -= 1
                else:
                    raise GpsdConnectionError()

            sleep(5)

    def shutdown(self):
        self._log.info("Shutting down %s...", self.name)
