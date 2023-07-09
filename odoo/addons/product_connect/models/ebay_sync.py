import os

from ebay_rest import API, DateTime, Error, Reference

from odoo import models, fields, api


class EbaySync(models.AbstractModel):
    _name = "ebay.sync"
    _description = "eBay Sync"

    # @api.model
    # def _setup_complete(self):
    #     super(EbaySync, self)._setup_complete()
    # application = {
    #     "app_id": "placeholder-placeholder-PRD-placeholder-placeholder",
    #     "cert_id": "PRD-placeholder-placeholder-placeholder-placeholder-placeholder",
    #     "dev_id": "placeholder-placeholder-placeholder-placeholder-placeholder",
    #     "redirect_uri": "placeholder-placeholder-placeholder-placeholder",
    # }

    # user = {
    #     "email_or_username": "<production-username>",
    #     "password": "<production-user-password>",
    #     "scopes": [
    #         "https://api.ebay.com/oauth/api_scope",
    #         "https://api.ebay.com/oauth/api_scope/sell.inventory",
    #         "https://api.ebay.com/oauth/api_scope/sell.marketing",
    #         "https://api.ebay.com/oauth/api_scope/sell.account",
    #         "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
    #     ],
    #     "refresh_token": "production-refresh_token",
    #     "refresh_token_expiry": "production-token_expiry",
    # }

    # header = {
    #     "accept_language": "en-US",
    #     "affiliate_campaign_id": "",
    #     "affiliate_reference_id": "",
    #     "content_language": "en-US",
    #     "country": "US",
    #     "currency": "USD",
    #     "device_id": "",
    #     "marketplace_id": "EBAY_US",
    #     "zip": "",
    # }

    # key_pair = {
    #     "private_key": "placeholder-placeholder-placeholder-placeholder-placeholder-plac",
    #     "signing_key_id": "placeholder-placeholder-placeholder-",
    # }

    # try:
    #     ebay_api = API(application=application, user=user, header=header)
    # except Error as error:
    #     print(f"Error {error.number} is {error.reason}  {error.detail}.\n")
    # else:
    #     try:
    #         print("The five least expensive iPhone things now for sale on-eBay:")
    #         for record in ebay_api.buy_browse_search(q="iPhone", sort="price", limit=5):
    #             if "record" not in record:
    #                 pass  # TODO Refer to non-records, they contain optimization information.
    #             else:
    #                 item = record["record"]
    #                 print(f"item id: {item['item_id']} {item['item_web_url']}")
    #     except Error as error:
    #         print(f"Error {error.number} is {error.reason} {error.detail}.\n")
    #     else:
    #         pass

    # os._exit(0)
