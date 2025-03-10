"""The Poolstation integration."""
from datetime import timedelta
import logging
from typing import Final

import aiohttp
from pypoolstation import Account, AuthenticationException, Pool

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from aiohttp import ClientError, ClientResponseError

from .const import COORDINATORS, DEVICES, DOMAIN, AUTH_RETRIES
from .util import create_account

PLATFORMS: Final = ["sensor", "number", "switch", "binary_sensor"]

_LOGGER: Final = logging.getLogger(__name__)

SCAN_INTERVAL: Final = timedelta(seconds=60)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Poolstation from a config entry."""
    session = async_create_clientsession(hass, cookie_jar=aiohttp.DummyCookieJar())
    account = Account(session, token=entry.data[CONF_TOKEN], logger=_LOGGER)

    _LOGGER.info("Pool station setup init.")

    try:
        pools = await Pool.get_all_pools(session, account=account)
    except aiohttp.ClientError as err:
        _LOGGER.warning("Pool station Client error: %s", err)
        raise ConfigEntryNotReady from err

    except AuthenticationException as err:
        _LOGGER.warning("Pool station Auth error: %s", err)
        account = create_account(
            session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], _LOGGER
        )
        try:
            token = await account.login()
        except AuthenticationException:
            _LOGGER.warning("Pool station Auth retry error: %s", err)
            # Unfortunately the poolstation API is crap and logging with wrong credentials returns a 500 instead of a 401
            # That's why this block is probably never being called. Instead the next except will.
            raise ConfigEntryAuthFailed from err
        except aiohttp.ClientResponseError:
            _LOGGER.warning("Pool station Client retry error: %s", err)
            raise ConfigEntryAuthFailed from err
        else:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_TOKEN: token,
                    CONF_EMAIL: entry.data[CONF_EMAIL],
                    CONF_PASSWORD: entry.data[CONF_PASSWORD],
                },
            )
            pools = await Pool.get_all_pools(session, account=account)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATORS: {},
        DEVICES: {},
    }

    for pool in pools:
        pool_id = pool.id
        coordinator = PoolstationDataUpdateCoordinator(hass, pool)
        await coordinator.async_config_entry_first_refresh()

        hass.data[DOMAIN][entry.entry_id][DEVICES][pool_id] = pool
        hass.data[DOMAIN][entry.entry_id][COORDINATORS][pool_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class PoolstationDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Poolstation device info."""

    def __init__(self, hass: HomeAssistant, pool: Pool) -> None:
        """Initialize global Poolstation data updater."""
        self.pool = pool
        self.auth_retries = AUTH_RETRIES  # Initialize auth_retries here
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{pool.alias}",
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> None:
        """Fetch data from poolstation.net."""
        _LOGGER.debug("Starting data update for pool: %s (auth_retries: %d)", self.pool.alias, self.auth_retries)
        try:
            await self.pool.sync_info()
            _LOGGER.debug("Successfully updated pool data for: %s (auth_retries: %d)", self.pool.alias, self.auth_retries)
            # reset counter
            self.auth_retries = AUTH_RETRIES
        except ClientResponseError as err:
            # ignore the error, most likely a server side timeout
            _LOGGER.warning("ClientResponse error while retrieving data for pool %s (auth_retries: %d): %s", self.pool.alias, self.auth_retries, err)
        except AuthenticationException as err:
            if self.auth_retries > 0:
                self.auth_retries -= 1
                _LOGGER.warning("Ignore authentication error", err)
            else:
                _LOGGER.warning("Max retries reached for pool %s (auth_retries: %d), raising authentication error: %s", self.pool.alias, self.auth_retries, err)
                raise ConfigEntryAuthFailed from err