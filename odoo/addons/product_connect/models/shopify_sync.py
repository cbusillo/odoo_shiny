import os
import datetime
import re
import base64
from dateutil.parser import parse
from dateutil.tz import tzutc
from pytz import utc

import shopify
import requests

from odoo import models, api


class ShopifySync(models.AbstractModel):
    _name = "shopify.sync"
    _description = "Shopify Sync"

    @api.model
    def sync_with_shopify(self):
        self.setup_shopify_session()
        self.import_from_shopify()

        self.export_to_shopify()

    @api.model
    def setup_shopify_session(self):
        shop_url = "yps-your-part-supplier"
        api_key = os.environ.get("SHOPIFY_API_KEY")
        token = os.environ.get("SHOPIFY_API_TOKEN")
        shopify.Session.setup(api_key=api_key, secret=token)
        shopify.ShopifyResource.set_site(f"https://{api_key}:{token}@{shop_url}.myshopify.com/admin")

    @api.model
    def import_from_shopify(self):
        import_time_last_str = self.env["ir.config_parameter"].sudo().get_param("shopify.import_time_last")

        import_time_start = datetime.datetime.now(tzutc())
        shopify_products = shopify.Product.find(updated_at_min=import_time_last_str)

        while shopify_products:
            for shopify_product in shopify_products:
                shopify_updated_at = parse(shopify_product.updated_at).astimezone(tzutc())

                # Search for the corxesponding Odoo product using the SKU
                odoo_product = self.env["product.product"].search([("shopify_product_id", "=", shopify_product.id)], limit=1)

                if odoo_product:
                    odoo_product_updated_at = odoo_product.write_date.replace(tzinfo=utc)

                    # If Shopify product is newer than Odoo product, import it
                    if shopify_updated_at > odoo_product_updated_at:
                        self.import_shopify_product(shopify_product)

                # If the product doesn't exist in Odoo yet, import it
                elif not odoo_product:
                    self.import_shopify_product(shopify_product)

            try:
                shopify_products = shopify_products.next_page()
            except IndexError:
                break

            self.env["ir.config_parameter"].sudo().set_param("shopify.import_time_last", import_time_start.isoformat())

    @api.model
    def import_shopify_product(self, shopify_product):
        if not shopify_product.variants:
            return

        shopify_product_variant = shopify_product.variants[0]
        # shopify_product_inventory = shopify.InventoryItem.find(shopify_product_variant.inventory_item_id)
        # shopify_cost = float(shopify_product_inventory.cost or 0.0)
        shopify_cost = 0.0

        shopify_sku_bin = (shopify_product.variants[0].sku or "").split("-")
        shopify_sku = shopify_sku_bin[0].strip()

        shopify_bin = shopify_sku_bin[1].strip() if len(shopify_sku_bin) > 1 else None
        shopify_mpn = shopify_product_variant.barcode

        if not re.match(r"^\d{4,8}$", shopify_sku):
            return

        if shopify_product.vendor:
            manufacturer = self.find_or_add_manufacturer(shopify_product.vendor)
        # Search for existing product
        odoo_product = self.env["product.product"].search([("default_code", "=", shopify_sku)], limit=1)

        odoo_condition = odoo_product.condition if odoo_product.condition else ""

        product_data = {
            "name": shopify_product.title,
            "barcode": "",
            "list_price": float(shopify_product_variant.price),
            "standard_price": shopify_cost,
            "mpn": shopify_mpn,
            "default_code": shopify_sku,
            "bin": shopify_bin,
            "description_sale": shopify_product.body_html,
            "weight": shopify_product_variant.weight,
            "detailed_type": "product",
            "is_published": True,
            "manufacturer": manufacturer.id if manufacturer else None,
            "condition": odoo_condition,
            "shopify_product_id": shopify_product.id,
        }

        if odoo_product:
            # Update product if it exists
            odoo_product.write(product_data)
        else:
            # Create product if it does not exist
            odoo_product = self.env["product.product"].create(product_data)

        odoo_product_template = self.env["product.template"].search([("id", "=", odoo_product.product_tmpl_id.id)], limit=1)

        if odoo_product_template.image_1920 is False or odoo_product_template.image_1920 is None:
            for index, shopify_image in enumerate(shopify_product.images):
                self.import_product_image(index, shopify_image, odoo_product_template)

        self.update_product_quantity_in_odoo(shopify_product.variants[0].inventory_quantity, odoo_product)

    @api.model
    def find_or_add_manufacturer(self, manufacturer_name):
        manufacturer = self.env["product.manufacturer"].search([("name", "=", manufacturer_name)], limit=1)

        if not manufacturer:
            manufacturer = self.env["product.manufacturer"].create({"name": manufacturer_name})

        return manufacturer

    @api.model
    def update_product_quantity_in_odoo(self, shopify_quantity, odoo_product):
        if shopify_quantity:
            odoo_product.update_quantity(shopify_quantity)

    @api.model
    def import_product_image(self, index, shopify_image, odoo_product_template):
        response = requests.get(shopify_image.src, timeout=10)
        image_base64 = base64.b64encode(response.content)
        self.env["product.image"].create(
            {
                "product_tmpl_id": odoo_product_template.id,
                "name": index,
                "image_1920": image_base64,
            }
        )

    @api.model
    def export_to_shopify(self):
        # Setup Shopify API

        export_time_last = self.env["ir.config_parameter"].sudo().get_param("shopify.export_time_last")
        export_time_start = datetime.datetime.now().isoformat()

        # Get all products from Odoo
        odoo_products = self.env["product.product"].search([("write_date", ">", export_time_last)])
        odoo_products = self.env["product.product"].search([("name", "ilike", "5006220")])
        # TODO: remove filter after testing single product

        for odoo_product in odoo_products:
            shopify_product = shopify.Product.find(odoo_product.shopify_product_id)
            if not shopify_product:
                # product doesn't exist in Shopify yet, so create a new one
                shopify_product = shopify.Product()

            # Set product data
            shopify_product.title = odoo_product.name
            shopify_product.body_html = "test" + odoo_product.description_sale
            shopify_product.vendor = odoo_product.manufacturer.name if odoo_product.manufacturer else None
            shopify_product.product_type = odoo_product.part_type.name

            # Create a variant for the product
            variant = shopify.Variant()
            variant.price = odoo_product.list_price
            variant.sku = f"{odoo_product.default_code} - {odoo_product.bin}"
            variant.barcode = odoo_product.mpn
            variant.inventory_management = "shopify"
            # if variant.inventory_quantity is None:
            # need to check for existing inventory before updating.
            #    variant.inventory_quantity = odoo_product.qty_available
            variant.weight = odoo_product.weight

            # Assign the variant data to the product
            shopify_product.variants = [variant]

            shopify_product.save()  # returns False if the record couldn't be saved
        self.env["ir.config_parameter"].sudo().set_param("shopify.export_time_last", export_time_start)
