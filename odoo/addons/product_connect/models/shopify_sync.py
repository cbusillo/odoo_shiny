import os
from datetime import datetime, timedelta
import re
import base64
import time
from dateutil.parser import parse
from dateutil.tz import tzutc
from pytz import utc
import pyactiveresource.connection

import shopify
import requests

from odoo import models, api, fields


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

        import_time_start = datetime.now(tzutc())
        import_time_last = parse(import_time_last_str).astimezone(tzutc())
        shopify_products = shopify.Product.find(updated_at_min=import_time_last_str)

        while shopify_products:
            for shopify_product in shopify_products:
                shopify_updated_at = parse(shopify_product.updated_at).astimezone(tzutc())

                # Search for the coresponding Odoo product using the SKU
                odoo_product_product = self.env["product.product"].search([("shopify_product_id", "=", shopify_product.id)], limit=1)

                if odoo_product_product:
                    odoo_product_template = odoo_product_product.product_tmpl_id
                    odoo_product_product_write_date = (
                        odoo_product_product.write_date.replace(tzinfo=utc) if odoo_product_product.write_date else None
                    )
                    odoo_product_template_write_date = (
                        odoo_product_template.write_date.replace(tzinfo=utc) if odoo_product_template.write_date else None
                    )
                    odoo_product_product_shopify_last_exported = (
                        odoo_product_product.shopify_last_exported.replace(tzinfo=utc)
                        if odoo_product_product.shopify_last_exported
                        else None
                    )
                    if import_time_last.year < 2001:
                        latest_write_date = datetime(2000, 1, 1, tzinfo=utc)
                    else:
                        latest_write_date = max(
                            filter(
                                None,
                                [
                                    odoo_product_product_write_date,
                                    odoo_product_template_write_date,
                                    odoo_product_product_shopify_last_exported,
                                ],
                            )
                        )

                    # If Shopify product is newer than Odoo product, import it
                    if shopify_updated_at > latest_write_date:
                        self.import_shopify_product(shopify_product)

                # If the product doesn't exist in Odoo yet, import it
                elif not odoo_product_product:
                    self.import_shopify_product(shopify_product)
                time.sleep(0.5)

            try:
                shopify_products = shopify_products.next_page()
            except IndexError:
                self.env["ir.config_parameter"].sudo().set_param("shopify.import_time_last", import_time_start.isoformat())
                break

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
        else:
            manufacturer = None

        if shopify_product.product_type:
            part_type = self.find_or_add_product_type(shopify_product.product_type)
        else:
            part_type = None
        # Search for existing product
        odoo_product = self.env["product.product"].search([("default_code", "=", shopify_sku)], limit=1)

        shopify_condition = None
        metafields = shopify_product.metafields()
        for metafield in metafields:
            if metafield.key == "condition":
                shopify_condition = metafield.value
                break

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
            "is_published": True if shopify_product.status.lower() == "active" else False,
            "manufacturer": manufacturer.id if manufacturer else None,
            "condition": shopify_condition
            if odoo_product.product_tmpl_id.is_condition_valid(shopify_condition)
            else odoo_product.condition,
            "shopify_product_id": shopify_product.id,
            "part_type": part_type.id if part_type else None,
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
    def find_or_add_product_type(self, product_type_name):
        product_type = self.env["product.type"].search([("name", "=", product_type_name)], limit=1)

        if not product_type:
            product_type = self.env["product.type"].create({"name": product_type_name})

        return product_type

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
    def export_product_image(self, shopify_product_id, odoo_image, index):
        shopify.Image.create(
            {
                "product_id": shopify_product_id,
                "position": index,
                "attachment": odoo_image.image_1920.decode("utf-8"),
            }
        )

    @api.model
    def export_to_shopify(self):
        # Setup Shopify API

        import_time_last_str = self.env["ir.config_parameter"].sudo().get_param("shopify.import_time_last")
        import_time_last = parse(import_time_last_str).astimezone(tzutc())

        export_time_last_str = self.env["ir.config_parameter"].sudo().get_param("shopify.export_time_last")
        export_time_last = datetime.strptime(export_time_last_str, "%Y-%m-%dT%H:%M:%S.%f%z")
        export_time_last = export_time_last - timedelta(minutes=5)
        export_time_last_str = export_time_last.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        export_time_start = datetime.now(tzutc())

        # Get all products from Odoo
        odoo_products = self.env["product.product"].search(
            [
                "|",
                ("write_date", ">", export_time_last_str),
                ("product_tmpl_id.write_date", ">", export_time_last_str),
            ]
        )

        for odoo_product in odoo_products:
            odoo_product_product_write_date = odoo_product.write_date.replace(tzinfo=utc) if odoo_product.write_date else None
            odoo_product_template_write_date = (
                odoo_product.product_tmpl_id.write_date.replace(tzinfo=utc) if odoo_product.product_tmpl_id.write_date else None
            )
            if odoo_product_product_write_date < import_time_last or odoo_product_template_write_date < import_time_last:
                continue
            try:
                if odoo_product.shopify_product_id:
                    shopify_product = shopify.Product.find(odoo_product.shopify_product_id)
                else:
                    raise AttributeError
            except (pyactiveresource.connection.ResourceNotFound, AttributeError):
                shopify_product = shopify.Product()

            # Set product data
            shopify_product.title = odoo_product.name
            shopify_product.body_html = odoo_product.description_sale
            shopify_product.vendor = odoo_product.manufacturer.name if odoo_product.manufacturer else None
            shopify_product.product_type = odoo_product.part_type.name if odoo_product.part_type else None
            shopify_product.status = "active" if odoo_product.is_published and odoo_product.qty_available > 0 else "draft"

            if hasattr(shopify_product, "variants") and shopify_product.variants:
                variant = shopify_product.variants[0]
            else:
                variant = shopify.Variant()
            variant.price = odoo_product.list_price
            variant.sku = f"{odoo_product.default_code} - {odoo_product.bin}"
            variant.barcode = odoo_product.mpn
            variant.inventory_management = "shopify"

            variant.weight = odoo_product.weight
            shopify_product.variants = [variant]

            shopify_product.save()  # returns False if the record couldn't be saved
            metafields = shopify.Metafield.find(owner_resource="product", owner_id=shopify_product.id)
            if hasattr(odoo_product, "condition") and odoo_product.condition:
                condition_metafield = next((mf for mf in metafields if mf.key == "condition"), None)

                if condition_metafield:
                    # Update existing metafield
                    condition_metafield.value = odoo_product.condition
                    condition_metafield.save()
                else:
                    # Create new metafield
                    condition_metafield = shopify.Metafield()
                    condition_metafield.key = "condition"
                    condition_metafield.value = odoo_product.condition
                    condition_metafield.type = "single_line_text_field"
                    condition_metafield.namespace = "custom"
                    condition_metafield.owner_resource = "product"
                    condition_metafield.owner_id = shopify_product.id
                    condition_metafield.save()

            if not odoo_product.shopify_product_id:
                locations = shopify.Location.find()
                location_id = locations[0].id
                inventory_item_id = shopify_product.variants[0].inventory_item_id
                shopify.InventoryLevel.adjust(location_id, inventory_item_id, int(odoo_product.qty_available))

                for odoo_image in sorted(
                    odoo_product.product_tmpl_id.product_template_image_ids, key=lambda image: image.name, reverse=True
                ):
                    self.export_product_image(shopify_product.id, odoo_image, odoo_image.name)

            odoo_product.write(
                {
                    "shopify_last_exported": fields.Datetime.now(),
                    "shopify_product_id": shopify_product.id,
                }
            )
            time.sleep(0.5)

        self.env["ir.config_parameter"].sudo().set_param("shopify.export_time_last", export_time_start.isoformat())
