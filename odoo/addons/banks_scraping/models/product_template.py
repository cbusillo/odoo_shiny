import base64
import os


import requests
import shopify


from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bin = fields.Char()
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
        products = shopify.Product.find()
        while products:
            # Loop over all products
            for shopify_product in products:
                # Extract required data
                product_data = {
                    "name": shopify_product.title,
                    "barcode": "",
                    "list_price": float(shopify_product.variants[0].price) if shopify_product.variants else 0.0,
                    "default_code": shopify_product.variants[0].barcode if shopify_product.variants else None,
                    "description_sale": shopify_product.body_html,
                    "weight": shopify_product.variants[0].weight if shopify_product.variants else None,
                    # "brand": "Shopify",  # Set a default brand, replace this with real data if available
                }

                # Search for existing product
                product = self.search([("name", "=", product_data["name"])], limit=1)

                # Get main image and encode it to base64
                image_1920 = getattr(product, "image_1920", None)
                if shopify_product.images and (not product or not isinstance(image_1920, bytes)):
                    response = requests.get(shopify_product.images[0].src, timeout=10)
                    image_base64 = base64.b64encode(response.content)
                    product_data["image_1920"] = image_base64

                if product:
                    # Update product if it exists
                    product.write(product_data)
                else:
                    # Create product if it does not exist
                    product = self.create(product_data)

                # Update vendor/supplier info
                if shopify_product.vendor:
                    # Search for existing partner with the same name as the vendor
                    partner = self.env["res.partner"].search([("name", "=", shopify_product.vendor)], limit=1)
                    if not partner:
                        # Create a new partner if it doesn't exist
                        partner = self.env["res.partner"].create({"name": shopify_product.vendor})

                    # Search for existing supplier info for this product and partner
                    supplierinfo = self.env["product.supplierinfo"].search(
                        [("product_tmpl_id", "=", product.id), ("partner_id", "=", partner.id)], limit=1
                    )
                    if not supplierinfo:
                        # Create new supplier info if it doesn't exist
                        self.env["product.supplierinfo"].create({"partner_id": partner.id, "product_tmpl_id": product.id})

            # Go to next page of products
            if products.has_next_page:
                products = products.next_page()
                self.env.cr.commit()  # pylint: disable=invalid-commit

            if products.has_next_page:
                products = products.next_page()
            else:
                products = False
