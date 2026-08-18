import asyncio
import logging
from functools import partial

import requests

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

EFFECT_STATIC = "static"
EFFECT_BREATHING = "breathing"
EFFECT_RAINBOW = "rainbow"
EFFECT_CHASING = "chasing"
EFFECT_WIPE = "wipe"
EFFECT_BOUNCE = "bounce"
EFFECT_ALERT = "alert"
EFFECT_NOTIFICATION = "notification"

EFFECTS = [
    EFFECT_STATIC,
    EFFECT_BREATHING,
    EFFECT_RAINBOW,
    EFFECT_CHASING,
    EFFECT_WIPE,
    EFFECT_BOUNCE,
    EFFECT_ALERT,
    EFFECT_NOTIFICATION,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    """Register the WallPanel LED entity."""
    host = entry.data["host"]

    async_add_entities([
        WallPanelLight(hass, host),
    ])


class WallPanelLight(LightEntity):
    """Representation of the WallPanel LED light."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
    ) -> None:
        self.hass = hass
        self._host = host
        self._state = False
        self._rgb = (255, 255, 255)
        self._brightness = 255
        self._effect = EFFECT_STATIC

    @property
    def unique_id(self) -> str:
        return f"wallpanel_control_led_light_{self._host}"

    @property
    def name(self) -> str:
        return "Tablet Flur OG LED"

    @property
    def is_on(self) -> bool:
        return self._state

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        return {ColorMode.RGB}

    @property
    def color_mode(self) -> ColorMode:
        return ColorMode.RGB

    @property
    def rgb_color(self) -> tuple[int, int, int]:
        return self._rgb

    @property
    def brightness(self) -> int:
        return self._brightness

    @property
    def effect_list(self) -> list[str]:
        return EFFECTS

    @property
    def effect(self) -> str | None:
        return self._effect

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "Tablet Flur OG",
            "manufacturer": "WallPanel Manufacturer",
            "model": "WallPanel with WS2812 LEDs",
            "sw_version": "1.0.0",
        }

    def _scaled_rgb(self) -> tuple[int, int, int]:
        """Apply Home Assistant brightness."""
        scale = (
            self._brightness / 255
            if self._brightness
            else 0
        )

        return (
            round(self._rgb[0] * scale),
            round(self._rgb[1] * scale),
            round(self._rgb[2] * scale),
        )

    def _color_hex(self) -> str:
        """Return the current scaled color as RRGGBB."""
        r, g, b = self._scaled_rgb()
        return f"{r:02X}{g:02X}{b:02X}"

    def _perform_request(
        self,
        path: str,
        params: dict[str, object],
    ) -> bool:
        """Perform a blocking HTTP request."""
        url = f"http://{self._host}:8080{path}"

        try:
            response = requests.get(
                url,
                params=params,
                timeout=3,
            )
            response.raise_for_status()

            _LOGGER.debug(
                "WallPanel response: %s %s",
                response.url,
                response.text,
            )
            return True

        except requests.RequestException as error:
            _LOGGER.warning(
                "WallPanel request failed: %s: %s",
                url,
                error,
            )
            return False

    async def _async_request(
        self,
        path: str,
        params: dict[str, object],
    ) -> bool:
        """Run the blocking request outside the event loop."""
        return await self.hass.async_add_executor_job(
            partial(
                self._perform_request,
                path,
                params,
            )
        )

    async def _async_send_static_color(self) -> bool:
        """Send a static color."""
        return await self._async_request(
            "/setLED",
            {
                "color": self._color_hex(),
            },
        )

    async def _async_send_effect(
        self,
        effect: str,
    ) -> bool:
        """Send an effect to the Android WallPanel."""
        params: dict[str, object] = {
            "effect": effect,
            "color": self._color_hex(),
            "cycles": 3,
        }

        if effect == EFFECT_BREATHING:
            params.update({
                "speed": 2,
            })

        elif effect == EFFECT_RAINBOW:
            params = {
                "effect": effect,
                "speedMs": 50,
                "cycles": 2,
            }

        elif effect == EFFECT_CHASING:
            params.update({
                "background": "141414",
                "activeLen": 10,
                "speedMs": 30,
                "cycles": 1,
            })

        elif effect == EFFECT_WIPE:
            params.update({
                "background": "000000",
                "activeLen": 1,
                "speedMs": 50,
                "cycles": 1,
            })

        elif effect == EFFECT_BOUNCE:
            params.update({
                "background": "000010",
                "activeLen": 5,
                "speedMs": 30,
                "cycles": 2,
            })

        elif effect == EFFECT_ALERT:
            params.update({
                "freqHz": 2,
                "flashes": 5,
            })

        elif effect == EFFECT_NOTIFICATION:
            params.update({
                "maxBrightness": 50,
                "cycles": 3,
            })

        else:
            _LOGGER.error(
                "Unsupported WallPanel effect: %s",
                effect,
            )
            return False

        return await self._async_request(
            "/setEffect",
            params,
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the LED on."""
        rgb_color = kwargs.get(ATTR_RGB_COLOR)

        if rgb_color is not None:
            self._rgb = tuple(
                max(0, min(255, int(value)))
                for value in rgb_color
            )

        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is not None:
            self._brightness = max(
                0,
                min(255, int(brightness)),
            )

        effect = kwargs.get(ATTR_EFFECT)

        if effect and effect != EFFECT_STATIC:
            success = await self._async_send_effect(effect)
            self._effect = effect
        else:
            success = await self._async_send_static_color()
            self._effect = EFFECT_STATIC

        if success:
            self._state = True
            self.async_write_ha_state()

            _LOGGER.debug(
                "WallPanel LED ON: rgb=%s brightness=%s effect=%s",
                self._rgb,
                self._brightness,
                self._effect,
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the LED off."""
        success = await self._async_request(
            "/setLED",
            {
                "color": "0",
            },
        )

        if success:
            self._state = False
            self._effect = EFFECT_STATIC
            self.async_write_ha_state()

            _LOGGER.debug(
                "WallPanel LED OFF",
            )