import os
import logging
from pathlib import Path

from ebaysdk.trading import Connection

import ebaysdk.exception 

from odoo import models, api


class EbaySync(models.AbstractModel):
    _name = "ebay.sync"
    _description = "eBay Sync"

    @api.model
    def _setup_complete(self):
        super(EbaySync, self)._setup_complete()
        try:
            ebay_api = Connection(
                config_file=Path.home() / ".shiny" / "ebaysdk.yaml",
                debug=False,
            )
        except ebaysdk.exception.ConnectionError as error:
            logging.error(error)
            logging.error(error.response.dict())
        request = {
            "startTimeFrom": "2023-07-01T00:00:00.000Z",
            "startTimeTo": "2023-07-11T00:00:00.000Z",
        }

        response = ebay_api.execute("GetSellerList", request)
        for index, item in enumerate(response.dict()["ItemArray"]["Item"]):
            logging.info('%s: %s', index, item["ItemID"])

        os._exit(1)  # pylint: disable=protected-access
        return

