import requests
import logging
from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Register the Light entity in Home Assistant."""
    host = entry.data["host"]
    async_add_entities([WallPanelLight(host)])


class WallPanelLight(LightEntity):
    """Representation of the WallPanel LED light."""

    def __init__(self, host: str):
        self._host = host
        self._state = False
        self._rgb = (255, 255, 255)  # base RGB color (without brightness applied)
        self._brightness = 255       # brightness 0–255

    @property
    def unique_id(self):
        return f"wallpanel_light_{self._host}"

    @property
    def name(self):
        return "WallPanel LED"

    @property
    def is_on(self):
        return self._state

    @property
    def supported_color_modes(self):
        return {ColorMode.RGB}

    @property
    def color_mode(self):
        return ColorMode.RGB

    @property
    def rgb_color(self):
        return self._rgb

    @property
    def brightness(self):
        return self._brightness

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "WallPanel",
            "manufacturer": "WallPanel Manufacturer",
            "model": "WallPanel Model",
            "sw_version": "1.0.0",
        }

    def _send_color(self, r: int, g: int, b: int):
        """Send RGB color to the panel via HTTP."""
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        url = f"http://{self._host}:8080/setLED?color={hex_color}"
        _LOGGER.debug("Sending color to %s: %s", self._host, hex_color)
        try:
            requests.get(url, timeout=3)
        except Exception as e:
            _LOGGER.warning(
                "Error while sending color to %s: %s", self._host, e
            )

    def _apply_and_send(self):
        """Scale base color according to brightness and send it."""
        scale = self._brightness / 255 if self._brightness else 0
        r = round(self._rgb[0] * scale)
        g = round(self._rgb[1] * scale)
        b = round(self._rgb[2] * scale)
        self._send_color(r, g, b)

    def turn_on(self, **kwargs):
        """Turn the LED on with the given color and brightness."""
        if "rgb_color" in kwargs and kwargs["rgb_color"] is not None:
            self._rgb = tuple(int(x) for x in kwargs["rgb_color"])

        if ATTR_BRIGHTNESS in kwargs and kwargs[ATTR_BRIGHTNESS] is not None:
            self._brightness = int(kwargs[ATTR_BRIGHTNESS])

        self._apply_and_send()
        self._state = True
        _LOGGER.debug(
            "WallPanel LED ON: rgb=%s brightness=%s",
            self._rgb,
            self._brightness,
        )

    def turn_off(self, **kwargs):
        """Turn the LED off (set color to 000000)."""
        self._send_color(0, 0, 0)
        self._state = False
        _LOGGER.debug("WallPanel LED OFF")
