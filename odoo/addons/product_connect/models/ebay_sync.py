import os
import logging
from pathlib import Path

from ebay_rest import API, Error

from odoo import models, api


class EbaySync(models.AbstractModel):
    _name = "ebay.sync"
    _description = "eBay Sync"

    @api.model
    def _setup_complete(self):
        super(EbaySync, self)._setup_complete()
        try:
            ebay_api = API(application="production_1", user="production_1", path=Path.home() / ".shiny", header="US")
        except Error as error:
            logging.fatal(error)
            os._exit(1)  # pylint: disable=protected-access
        try:
            for record in ebay_api.buy_browse_search(q="iphone", sort="price", limit=10):
                if "record" not in record:
                    continue
                logging.info(record["record"].get("title", "No title"))

            for record in ebay_api.sell_inventory_get_inventory_items(limit=10):
                if "record" not in record:
                    continue
                logging.info(record["record"].get("product").get("title", "No title"))
        except Error as error:
            logging.fatal(error)
        finally:
            os._exit(1)  # pylint: disable=protected-access
        return
