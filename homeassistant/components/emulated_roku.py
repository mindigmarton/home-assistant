import asyncio
import logging
import voluptuous as vol

DOMAIN = 'emulated_roku'

REQUIREMENTS = ['aiohttp==2.3.3', 'shortuuid==0.5.0', 'emulated_roku==0.0.3']

_LOGGER = logging.getLogger(__name__)

CONNECTION_TIMEOUT = 10

CONF_HOST_IP = 'host_ip'
CONF_LISTEN_PORTS = 'listen_ports'
CONF_ADVERTISE_IP = 'advertise_ip'
CONF_UPNP_BIND_MULTICAST = 'upnp_bind_multicast'

DEFAULT_HOST_IP = "0.0.0.0"
DEFAULT_LISTEN_PORTS = [8060]
DEFAULT_UPNP_BIND_MULTICAST = True

import homeassistant.helpers.config_validation as cv

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST_IP, default=DEFAULT_HOST_IP): cv.string,
        vol.Optional(CONF_LISTEN_PORTS, default=DEFAULT_LISTEN_PORTS): cv.ensure_list,
        vol.Optional(CONF_ADVERTISE_IP): cv.string,
        vol.Optional(CONF_UPNP_BIND_MULTICAST, default=DEFAULT_UPNP_BIND_MULTICAST): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def async_setup(hass, config):
    """Setup the emulated roku component."""
    from emulated_roku import RokuDiscoveryServerProtocol, RokuEventHandler, make_roku_api
    from homeassistant.const import (
        EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    )

    config = config.get(DOMAIN)

    _LOGGER.info("Initializing emulated roku")

    host_ip = config.get(CONF_HOST_IP)
    listen_ports = config.get(CONF_LISTEN_PORTS)
    advertise_ip = config.get(CONF_ADVERTISE_IP) or host_ip
    bind_multicast = config.get(CONF_UPNP_BIND_MULTICAST)

    class HomeAssistantRokuEventHandler(RokuEventHandler):
        DATA_EVENT_TYPE = 'type'
        DATA_ROKU_USN = 'roku_usn'
        DATA_KEY = 'key'

        COMMAND_KEYDOWN = 'keydown'
        COMMAND_KEYUP = 'keyup'
        COMMAND_KEYPRESS = 'keypress'

        def __init__(self, hass):
            self.hass = hass

        def on_keydown(self, roku_usn, key):
            self.hass.bus.async_fire('roku_command', {
                self.DATA_ROKU_USN: roku_usn,
                self.DATA_EVENT_TYPE: self.COMMAND_KEYDOWN,
                self.DATA_KEY: key
            })

        def on_keyup(self, roku_usn, key):
            self.hass.bus.async_fire('roku_command', {
                self.DATA_ROKU_USN: roku_usn,
                self.DATA_EVENT_TYPE: self.COMMAND_KEYUP,
                self.DATA_KEY: key
            })

        def on_keypress(self, roku_usn, key):
            self.hass.bus.async_fire('roku_command', {
                self.DATA_ROKU_USN: roku_usn,
                self.DATA_EVENT_TYPE: self.COMMAND_KEYPRESS,
                self.DATA_KEY: key
            })

    servers = []

    @asyncio.coroutine
    def start_emulated_roku(event):
        handler = HomeAssistantRokuEventHandler(hass)

        for port in listen_ports:
            advertise_port = None
            if type(port) is not int:
                port, advertise_port = port.split(":")

                port = int(port)
                advertise_port = int(advertise_port)
            else:
                advertise_port = port

            _LOGGER.info("Intializing emulated roku api %s:%s", host_ip, port)
            discovery_endpoint, roku_api_endpoint = make_roku_api(hass.loop, handler,
                                                                  host_ip, port,
                                                                  advertise_ip, advertise_port,
                                                                  bind_multicast)

            discovery_server, _ = yield from discovery_endpoint
            api_server = yield from roku_api_endpoint

            servers.append(discovery_server)
            servers.append(api_server)

    @asyncio.coroutine
    def stop_emulated_roku(event):
        _LOGGER.info("Closing emulated roku server.")
        for server in servers:
            server.close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop_emulated_roku)
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_emulated_roku)

    return True
