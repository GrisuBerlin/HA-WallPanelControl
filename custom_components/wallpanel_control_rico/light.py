import logging
from functools import partial

import requests

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
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
    async_add_entities(
        [WallPanelLight(hass, entry.data["host"])]
    )


class WallPanelLight(LightEntity):
    """Representation of the WallPanel LED light."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        self.hass = hass
        self._host = host
        self._state = False
        self._rgb = (255, 255, 255)
        self._brightness = 255
        self._effect = EFFECT_STATIC

    @property
    def unique_id(self) -> str:
        return f"wallpanel_control_rico_led_{self._host}"

    @property
    def name(self) -> str:
        return "LED"

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
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "WallPanel 32",
            "manufacturer": "WallPanel Manufacturer",
            "model": "WallPanel WS2812",
            "sw_version": "1.0.2",
        }

    @property
    def supported_features(self) -> LightEntityFeature:
        return LightEntityFeature.EFFECT

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
        """Run requests outside the Home Assistant event loop."""
        return await self.hass.async_add_executor_job(
            partial(
                self._perform_request,
                path,
                params,
            )
        )

    def _scaled_rgb(self) -> tuple[int, int, int]:
        scale = self._brightness / 255 if self._brightness else 0

        return (
            round(self._rgb[0] * scale),
            round(self._rgb[1] * scale),
            round(self._rgb[2] * scale),
        )

    def _color_hex(self) -> str:
        r, g, b = self._scaled_rgb()
        return f"{r:02X}{g:02X}{b:02X}"

    async def _async_send_static(self) -> bool:
        return await self._async_request(
            "/setLED",
            {"color": self._color_hex()},
        )

    async def _async_send_effect(self, effect: str) -> bool:
        params: dict[str, object] = {
            "effect": effect,
            "cycles": 1,
            "color": self._color_hex(),
        }

        if effect == EFFECT_BREATHING:
            params.update({"speed": 2})
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
            _LOGGER.error("Unsupported effect: %s", effect)
            return False

        return await self._async_request(
            "/setEffect",
            params,
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the LED on with color, brightness, or effect."""
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
            if success:
                self._effect = effect
        else:
            success = await self._async_send_static()
            if success:
                self._effect = EFFECT_STATIC

        if success:
            self._state = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the LED off."""
        success = await self._async_request(
            "/setLED",
            {"color": "0"},
        )

        if success:
            self._state = False
            self._effect = EFFECT_STATIC
            self.async_write_ha_state()
