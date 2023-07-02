import base64
import os
import time

import requests
import shopify


from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bin = fields.Char()
    mpn = fields.Char(string="MPN")
    product_scraper_id = fields.Many2one(
        "product.scraper", compute="_compute_product_scraper_id", store=True, readonly=False, string="Product Scraper"
    )
    product_scraper_html = fields.Text(related="product_scraper_id.source_url_html", string="Product Scraper HTML", readonly=True)
    combined_description = fields.Html(compute="_compute_combined_description", readonly=True)

    @api.depends("description_sale", "product_scraper_html")
    def _compute_combined_description(self):
        for record in self:
            record.combined_description = f"{record.description_sale or ''} {record.product_scraper_html or ''}"

    @api.depends("default_code")
    def _compute_product_scraper_id(self):
        for record in self:
            sku = (record.default_code or "").split(" ")[0]
            if sku:
                product_scraper = self.env["product.scraper"].search([("sku", "=", sku)], limit=1)
                record.product_scraper_id = product_scraper

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
                shopify_product_inventory = shopify.InventoryItem.find(shopify_product_variant.inventory_item_id)
                # Extract required data
                shopify_sku_bin = (shopify_product.variants[0].sku or "").split("-")
                shopify_sku = shopify_sku_bin[0].strip()
                shopify_metafields = shopify.Metafield.find(resource_id=shopify_product.id, resource="products")
                for metafield in shopify_metafields:
                    if metafield.key == "bin":
                        shopify_bin = metafield.value
                    if metafield.key == "mpn":
                        shopify_mpn = metafield.value
                if len(shopify_sku_bin) > 1 and shopify_bin is None:
                    shopify_bin = shopify_sku_bin[1].strip()

                if shopify_mpn is None:
                    shopify_mpn = shopify_product_variant.barcode

                product_data = {
                    "name": shopify_product.title,
                    "barcode": "",
                    "list_price": float(shopify_product_variant.price),
                    "standard_price": float(shopify_product_inventory.cost or 0),
                    "mpn": shopify_mpn,
                    "default_code": shopify_sku,
                    "bin": shopify_bin,
                    "description_sale": shopify_product.body_html,
                    "weight": shopify_product_variant.weight,
                    "type": "product",
                    "is_published": True,
                }

                # Search for existing product
                odoo_product = self.env["product.product"].search([("default_code", "=", shopify_sku)], limit=1)

                # Get main image and encode it to base64
                image_1920 = getattr(odoo_product, "image_1920", None)
                if shopify_product.images and (not odoo_product or not isinstance(image_1920, bytes)):
                    response = requests.get(shopify_product.images[0].src, timeout=10)
                    image_base64 = base64.b64encode(response.content)
                    product_data["image_1920"] = image_base64

                if odoo_product:
                    # Update product if it exists
                    odoo_product.write(product_data)
                else:
                    # Create product if it does not exist
                    odoo_product = self.create(product_data)

                # Update vendor/supplier info
                if shopify_product.vendor:
                    # Search for existing partner with the same name as the vendor
                    partner = self.env["res.partner"].search([("name", "=", shopify_product.vendor)], limit=1)
                    if not partner:
                        # Create a new partner if it doesn't exist
                        partner = self.env["res.partner"].create({"name": shopify_product.vendor})

                    # Search for existing supplier info for this product and partner
                    supplierinfo = self.env["product.supplierinfo"].search(
                        [("product_tmpl_id", "=", odoo_product.id), ("partner_id", "=", partner.id)], limit=1
                    )
                    if not supplierinfo:
                        # Create new supplier info if it doesn't exist
                        self.env["product.supplierinfo"].create({"partner_id": partner.id, "product_tmpl_id": odoo_product.id})

                self.env.cr.commit()  # pylint: disable=invalid-commit

                if shopify_product.variants[0].inventory_quantity:
                    # Get the Stock location
                    stock_location = self.env.ref("stock.stock_location_stock")

                    # Find the quant for this product in the Stock location
                    quant = self.env["stock.quant"].search(
                        [
                            ("product_id", "=", odoo_product.id),
                            ("location_id", "=", stock_location.id),
                        ],
                        limit=1,
                    )

                    if not quant:
                        # Create a new quant if none exists
                        quant = self.env["stock.quant"].create(
                            {
                                "product_id": odoo_product.id,
                                "location_id": stock_location.id,
                            }
                        )

                    # Update the quantity in the quant
                    quant.with_context(inventory_mode=True).write(
                        {
                            "quantity": float(shopify_product.variants[0].inventory_quantity),
                        }
                    )
                time.sleep(0.5)  # Pause for 500ms
            # Go to next page of products
            if shopify_products.has_next_page:
                shopify_products = shopify_products.next_page()
                self.env.cr.commit()  # pylint: disable=invalid-commit

            if shopify_products.has_next_page:
                shopify_products = shopify_products.next_page()
            else:
                shopify_products = False
