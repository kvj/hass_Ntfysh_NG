from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.exceptions import HomeAssistantError

import aiohttp
import asyncio

import json

from aiohttp_sse_client import client as sse_client
from urllib.parse import urljoin

from .constants import DOMAIN

import logging

_LOGGER = logging.getLogger(__name__)

async def async_rest_status_code(url: str, path: str, headers: dict = {}, method: str = "GET", body = None):
    try:
        async with aiohttp.ClientSession() as session:
            data = {}
            if body:
                data = open(body["filename"], "rb")
            async with session.request(method=method, url=urljoin(url, path), headers=headers, data=data) as response:
                if not response.ok:
                    _LOGGER.warn(f"async_rest_status_code: result: {url} {path}: {response.status}: {response.reason} / {response.headers}")
                    resp_text = await response.text()
                    _LOGGER.warn(f"async_rest_status_code: text: {resp_text}")
                else:
                    _LOGGER.debug(f"async_rest_status_code: {url} {path}: {response.status}: {response.reason} / {response.headers}")
                return response.status
    except Exception as e:
        _LOGGER.error("async_rest_status_code: error making Rest request", e)
    return 500


class Coordinator(DataUpdateCoordinator):

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._async_update,
        )
        self._entry = entry
        self._config = entry.as_dict()["options"]
        self._title = entry.as_dict()["data"]["title"]
        self._sse_source = None
        self.__listeners = []

    async def _async_update(self):
        return {}

    async def async_load(self):
        _LOGGER.debug(f"async_load: ")
        self._loaded = True
        topics = self._config["subscribe"].strip()
        self._topics = []
        if not topics:
            _LOGGER.info("async_load: No topics to subscribe to")
            return
        self._topics = [t.strip() for t in topics.split(",")]
        self._entry.async_create_background_task(self.hass, self._async_main_sse_loop(), "main_sse_loop")

    async def async_unload(self):
        _LOGGER.debug(f"async_unload: ")
        self._loaded = False
        if self._sse_source:
            await self._sse_source.close()
        self._listeners = []

    async def _async_main_sse_loop(self):
        _LOGGER.debug("_async_main_sse_loop: ")
        topics = self._config["subscribe"].strip()
        if not topics:
            _LOGGER.info("_async_main_sse_loop: No topics to subscribe to")
            return
        url_path = ",".join(self._topics)
        headers = {}
        if token := self._config["token"]:
            headers["authorization"] = f"Bearer {token}"
        async with aiohttp.ClientSession() as session:
            while True:
                if not self._loaded:
                    _LOGGER.info(f"_async_main_sse_loop: stopping loop")
                    self._sse_source = None
                    return
                try:
                    url = urljoin(self._config["url"], f"{url_path}/sse")
                    self._sse_source = sse_client.EventSource(url, headers=headers, session=session)
                    async with self._sse_source:
                        async for event in self._sse_source:
                            _LOGGER.debug(f"_async_main_sse_loop: event: {event}")
                            if not event.type:
                                try:
                                    json_data = json.loads(event.data)
                                    if "topic" in json_data and json_data["topic"] in self._topics:
                                        for l in self.__listeners:
                                            await l(json_data)
                                except:
                                    _LOGGER.error(f"_async_main_sse_loop: error parsing JSON data: {event.data}")
                    _LOGGER.debug(f"_async_main_sse_loop: closed connection")
                except:
                    _LOGGER.error("_async_main_sse_loop: error making SSE request")
                    await asyncio.sleep(10)
    
    def _add_listener(self, listener):
        self.__listeners.append(listener)

    async def async_notify(self, data):
        headers = {}
        body = None
        if val := data.get("title"):
            headers["x-title"] = val
        if val := data.get("message"):
            headers["x-message"] = val
        if "priority" in data:
            headers["x-priority"] = str(data["priority"])
        if val := data.get("tags"):
            headers["x-tags"] = val
        if val := data.get("delay"):
            headers["x-delay"] = val
        if val := data.get("actions"):
            headers["x-actions"] = val
        if val := data.get("click"):
            headers["x-click"] = val
        if val := data.get("icon"):
            headers["x-icon"] = val
        if val := data.get("attach"):
            headers["x-attach"] = val
        if val := data.get("attach-local"):
            body = {
                "filename": val, 
            }
        if val := data.get("filename"):
            headers["x-filename"] = val
        if val := data.get("email"):
            headers["x-email"] = val
        if val := data.get("call"):
            headers["x-call"] = str(val)
        if "markdown" in data:
            headers["x-markdown"] = "yes" if data["markdown"] else "no"
        if "cache" in data:
            headers["x-cache"] = "yes" if data["cache"] else "no"
        if "firebase" in data:
            headers["x-firebase"] = "yes" if data["firebase"] else "no"
        if val := data.get("content-type"):
            headers["content-type"] = val

        if token := self._config["token"]:
            headers["authorization"] = f"Bearer {token}"

        _LOGGER.debug(f"async_notify: {data}, {headers}, {body}")
        code = await async_rest_status_code(self._config["url"], data["topic"], headers=headers, body=body, method="PUT")
        _LOGGER.debug(f"async_notify: result: {code}")
        if code >= 400:
            raise HomeAssistantError(f"Http error: {code}")

class BaseEntity(CoordinatorEntity):

    def __init__(self, coordinator: Coordinator):
        super().__init__(coordinator)
        coordinator._add_listener(self.on_message)

    def with_name(self, name: str):
        self._attr_has_entity_name = True
        self._attr_unique_id = f"ntfysh_ng_{self.coordinator._title}_{name}"
        self._attr_name = name
        return self

    @property
    def device_info(self):
        return {
            "identifiers": {
                ("entry_id", self.coordinator._entry.entry_id), 
            },
            "name": self.coordinator._title,
        }

    async def on_message(self, message: dict):
        pass