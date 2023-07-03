import base64
import os
import re

import requests
import shopify


from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    _sql_constraints = [
        ("default_code_uniq", "unique (default_code)", "SKU already exists !"),
    ]

    def update_quantity(self, quantity):
        stock_location = self.env.ref("stock.stock_location_stock")
        for product in self:
            quant = self.env["stock.quant"].search(
                [("product_id", "=", product.id), ("location_id", "=", stock_location.id)], limit=1
            )

            if not quant:
                quant = self.env["stock.quant"].create({"product_id": product.id, "location_id": stock_location.id})

            quant.with_context(inventory_mode=True).write({"quantity": float(quantity)})

    @api.model
    def sync_shopify_products(self):
        # Setup Shopify API
        shop_url = "yps-your-part-supplier"
        api_key = os.environ.get("SHOPIFY_API_KEY")
        token = os.environ.get("SHOPIFY_API_TOKEN")

        shopify.Session.setup(api_key=api_key, secret=token)

        shopify.ShopifyResource.set_site(f"https://{api_key}:{token}@{shop_url}.myshopify.com/admin")

        # Retrieve all products from Shopify
        shopify_products = shopify.Product.find()

        while shopify_products:
            # Loop over all products
            for shopify_product in shopify_products:
                if not shopify_product.variants:
                    continue

                shopify_product_variant = shopify_product.variants[0]
                # shopify_product_inventory = shopify.InventoryItem.find(shopify_product_variant.inventory_item_id)
                shopify_cost = 0.0  # shopify_cost = float(shopify_product_inventory.cost or 0.0)
                # if hasattr(shopify_product_inventory, "cost") else 0.0
                # Extract required data
                shopify_sku_bin = (shopify_product.variants[0].sku or "").split("-")
                shopify_sku = shopify_sku_bin[0].strip()

                shopify_bin = shopify_sku_bin[1].strip() if len(shopify_sku_bin) > 1 else None
                shopify_mpn = shopify_product_variant.barcode

                if not re.match(r"^\d{4,8}$", shopify_sku):
                    continue

                if shopify_product.vendor:
                    manufacturer = self.env["product.manufacturer"].search([("name", "=", shopify_product.vendor)], limit=1)
                    if not manufacturer:
                        manufacturer = self.env["product.manufacturer"].create({"name": shopify_product.vendor})

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
                }

                # Search for existing product
                odoo_product = self.env["product.product"].search([("default_code", "=", shopify_sku)], limit=1)

                if odoo_product:
                    # Update product if it exists
                    odoo_product.write(product_data)
                else:
                    # Create product if it does not exist
                    odoo_product = self.create(product_data)

                odoo_product_template = self.env["product.template"].search([("id", "=", odoo_product.product_tmpl_id.id)], limit=1)

                if odoo_product_template.image_1920 is False or odoo_product_template.image_1920 is None:
                    for index, shopify_image in enumerate(shopify_product.images):
                        response = requests.get(shopify_image.src, timeout=10)
                        image_base64 = base64.b64encode(response.content)
                        if index == 0:
                            odoo_product_template.image_1920 = image_base64
                        self.env["product.images.extension"].create(
                            {
                                "product_id": odoo_product_template.id,
                                "image_1920": image_base64,
                            }
                        )

                if shopify_product.variants[0].inventory_quantity:
                    odoo_product.update_quantity(shopify_product.variants[0].inventory_quantity)

                # time.sleep(0.5)  # Pause for 500ms
            # Go to next page of products
            if shopify_products.has_next_page:
                shopify_products = shopify_products.next_page()
            else:
                shopify_products = False

            self.env.cr.commit()  # pylint: disable=invalid-commit
