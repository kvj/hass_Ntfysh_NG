from homeassistant.components import event

from .coordinator import BaseEntity
from .constants import DOMAIN

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_setup_entities):
    coordinator = hass.data[DOMAIN]["devices"][entry.entry_id]
    async_setup_entities([_Event(coordinator)])

class _Event(BaseEntity, event.EventEntity):

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self.with_name("Message")
        self._attr_event_types = coordinator._topics

    async def on_message(self, message: dict):
        _LOGGER.debug(f"on_message: {message}")
        self._trigger_event(message["topic"], {
            "instance": self.coordinator._title,
            **message
        })
        self.async_write_ha_state()
