import base64
import logging
import os
import re
from string import capwords
from urllib.parse import urlparse

import requests
import shopify
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_fixed

from odoo import api, fields, models

BASE_URL = "https://www.crowleymarine.com"


class ProductScraperURLState(models.Model):
    _name = "product.scraper.url.state"
    _description = "URL Scraping State"

    url = fields.Char(string="URL", required=True, index=True)
    scraped = fields.Boolean(default=False, index=True)

    _sql_constraints = [("url_unique", "UNIQUE(url)", "The URL must be unique!")]


class ProductScraperWizard(models.TransientModel):
    _name = "product.scraper.wizard"
    _description = "Product Scraper Wizard"

    def action_scrape_website(self):
        self.env["product.scraper"].scrape_website()
        return {"type": "ir.actions.act_window_close"}

    def action_sync_shopify_products(self):
        self.env["product.template"].sync_shopify_products()
        return {"type": "ir.actions.act_window_close"}


class ProductScraperSource(models.Model):
    _name = "product.scraper.source"
    _description = "Product Scraper Source URL"

    source_url = fields.Char(index=True, string="Source URL")
    source_url_display = fields.Char(compute="_compute_source_url_display", store=True, index=True)
    product_id = fields.Many2one("product.scraper", string="Related Product", index=True)

    _sql_constraints = [("product_source_unique", "UNIQUE(source_url, product_id)", "The Source URL must be unique per product!")]

    @api.depends("source_url")
    def _compute_source_url_display(self):
        for record in self:
            record.source_url = record.source_url or ""
            record.source_url_display = record.source_url.replace(BASE_URL, "")


class ProductScraper(models.Model):
    _name = "product.scraper"
    _description = "Product Scraper"

    name = fields.Char()
    source_url_ids = fields.One2many("product.scraper.source", "product_id", string="Source URL Count")
    source_url_count = fields.Integer(compute="_compute_source_url_count", store=True)
    source_url_list = fields.Text(compute="_compute_source_url_list", string="Source URLs List")
    source_url_html = fields.Text(compute="_compute_source_url_html", string="Source URLs HTML")
    url = fields.Char(string="URL", index=True)
    url_display = fields.Char(compute="_compute_url_display", string="Path")
    sku = fields.Char(required=True, string="SKU", index=True)
    price = fields.Float(index=True)
    brand = fields.Char(index=True)
    product_template_ids = fields.One2many("product.template", "product_scraper_id", string="Related Products")

    _sql_constraints = [("brand_sku_unique", "UNIQUE(brand, sku)", "The Brand and SKU must be unique!")]

    @api.depends("source_url_ids")
    def _compute_source_url_list(self):
        for record in self:
            record.source_url_list = "\n".join(url.source_url_display for url in record.source_url_ids)

    @api.depends("source_url_ids")
    def _compute_source_url_count(self):
        for rec in self:
            rec.source_url_count = len(rec.source_url_ids)

    @api.depends("url")
    def _compute_url_display(self):
        for record in self:
            record.url = record.url or ""
            record.url_display = record.url.replace(BASE_URL, "")

    @api.depends("source_url_ids")
    def _compute_source_url_html(self):
        def format_header(header):
            return f"<th style='border:1px solid black; padding:10px;'>{header}</th>"

        def format_cell(index, cell, cells_len):
            if index == cells_len - 2:
                return cell.upper()
            elif index == cells_len - 1:
                return capwords(cell).replace("-", " ")
            elif index == cells_len - 3:
                return cell.upper()
            else:
                return capwords(cell).replace("Oem-parts", "OEM")

        headers = ["Brand", "Type", "", "Year", "Model"]  # Replace with your actual headers
        header_row = f"<tr>{''.join(format_header(header) for header in headers)}</tr>"

        for record in self:
            urls = (url.source_url_display for url in record.source_url_ids)

            table_rows = []
            for url in urls:
                cells = url.split("/")[1:]  # Skip the first cell if it's blank
                formatted_cells = [format_cell(index, cell, len(cells)) for index, cell in enumerate(cells)]
                table_rows.append(
                    "<tr>"
                    + "".join(f"<td style='border:1px solid black; padding:10px;'>{cell}</td>" for cell in formatted_cells)
                    + "</tr>"
                )  # pylint: disable=consider-using-f-string

            record.source_url_html = f"<table style='border:1px solid black'>{header_row + ''.join(table_rows)}</table>"

    @api.model
    def scrape_website(self):
        visited_urls = set()
        visited_end_links = {}

        @retry(stop=stop_after_attempt(5), wait=wait_fixed(1))
        def get(url):
            response = requests.get(url, timeout=10)
            if response.status_code != 404:  # Only raise if status code is not 404
                response.raise_for_status()  # Raises a HTTPError if one occurred
            return response

        logger = logging.getLogger(__name__)

        def get_links_in_page(url: str, search_regex: str = r"/((19|20)\d{2}|ag|af|ab|aa)") -> list:
            if BASE_URL not in url:
                url = BASE_URL + url.replace("file://", "")

            if url in visited_urls and url != BASE_URL:
                logger.info("Already visited: %s", url)
                return []

            logger.info("Visiting: %s", url)
            try:
                response = get(url)
            except requests.exceptions.HTTPError as error:
                logger.error("Error during requests to %s : %s", url, str(error))
                return []
            soup = BeautifulSoup(response.text, "html.parser")
            visited_urls.add(url)

            links = [
                (BASE_URL + link.get("href")) if link.get("href").startswith("/") else link.get("href")
                for link in soup.find_all("a")
                if link.get("href")
            ]

            filtered_links = [link.split("?")[0].split("#")[0] for link in links if re.search(search_regex, link)]

            return filtered_links

        def get_links_in_page_year(url: str) -> list:
            return get_links_in_page(url)

        def get_links_in_page_product(url: str) -> list:
            return get_links_in_page(url, r"/products/")

        def get_links_in_page_main(url: str) -> list:
            return get_links_in_page(url, r"/oem-parts")

        for main_link in get_links_in_page_main(BASE_URL):
            if "oem-parts" not in main_link or "mercury" in main_link:
                continue
            for type_year_link in get_links_in_page_year(main_link):
                if "outboard" not in type_year_link and "international" not in type_year_link:
                    continue
                for motor_link in get_links_in_page_year(type_year_link):
                    url_state = self.env["product.scraper.url.state"].search([("url", "=", motor_link)], limit=1)
                    if url_state and url_state.scraped:
                        logger.info("Link %s already scraped, skipping...", motor_link)
                        continue
                    for part_link in get_links_in_page_year(motor_link):
                        if "/products/" in part_link:
                            continue
                        for end_link in get_links_in_page_product(part_link):
                            brand = capwords(urlparse(end_link).path.split("/")[1])
                            if end_link in visited_end_links:
                                product_data = visited_end_links[end_link]
                                sku = product_data["sku"]
                            else:
                                try:
                                    response = get(end_link)
                                except requests.exceptions.HTTPError as error:
                                    logger.error("Error during requests to %s : %s", end_link, str(error))
                                    continue
                                soup = BeautifulSoup(response.text, "html.parser")

                                sku_element = soup.select_one('small[itemprop="sku"], span[data-testid="product:sku"]')
                                if sku_element:
                                    sku = sku_element.text.strip()

                                price_element = soup.select_one('span[itemprop="price"]')
                                if price_element:
                                    price = price_element.text.strip()

                                if price:
                                    price = re.sub(r"[^\d\.]", "", str(price))
                                    if price == "":
                                        price = 0.0
                                    else:
                                        # Handle price ranges
                                        if "to" in price:
                                            price = [float(p) for p in price.split("to")][0]
                                        else:
                                            price = float(price)
                                else:
                                    price = 0.0
                                name_element = soup.select_one('span[itemprop="name"]')
                                if name_element:
                                    name = name_element.text.strip()
                                if not sku or price is None or not name:
                                    sku = sku or ".check-me"
                                if not name:
                                    name = ""

                                product_data = {
                                    "name": capwords(name),
                                    "url": end_link,
                                    "sku": sku,
                                    "price": price,
                                    "brand": brand,
                                }
                                logger.info("Checking product: %s", product_data)
                                visited_end_links[end_link] = product_data

                            # Search for existing product
                            product = self.search([("sku", "=", sku), ("brand", "=", brand)], limit=1)

                            if product:
                                # Update product if it exists
                                product.write(
                                    {
                                        "name": product_data["name"],
                                        "price": product_data["price"],
                                    }
                                )
                                logger.info("Updated product: %s", product_data)
                            else:
                                # Create product if it does not exist
                                product = self.create(product_data)
                                logger.info("Created new product: %s", product_data)
                                self.env.cr.commit()  # commit after creating a new product

                            # Check if source_url already exists for the product
                            source_exists = self.env["product.scraper.source"].search(
                                [("source_url", "=", part_link), ("product_id", "=", product.id)], limit=1
                            )

                            if not source_exists:
                                # Add source_url to product
                                self.env["product.scraper.source"].create(
                                    {
                                        "source_url": part_link,
                                        "product_id": product.id,
                                    }
                                )
                                logger.info("Added source URL %s to product %s", part_link, product.name)
                                self.env.cr.commit()  # commit after creating a new source URL
                            else:
                                logger.info("Source URL %s already exists for product %s", part_link, product.name)

                    if not url_state:
                        # if the URL wasn't previously in the database, create a new record
                        url_state = self.env["product.scraper.url.state"].create({"url": motor_link})
                    url_state.write({"scraped": True})
                    self.env.cr.commit()  #


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_scraper_id = fields.Many2one(
        "product.scraper", compute="_compute_product_scraper_id", store=True, readonly=False, string="Product Scraper"
    )
    product_scraper_html = fields.Text(related="product_scraper_id.source_url_html", string="Product Scraper HTML", readonly=True)

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
                if shopify_product.images and (not product or not product.image_1920):
                    response = requests.get(shopify_product.images[0].src, timeout=10)
                    image_base64 = base64.b64encode(response.content)
                    product_data["image_1920"] = image_base64

                if product:
                    # Prepare data to update
                    update_data = {
                        "name": product_data["name"],
                        "list_price": product_data["list_price"],
                        "default_code": product_data["default_code"],
                        "barcode": product_data["barcode"],
                        "description_sale": product_data["description_sale"],
                        "weight": product_data["weight"],
                    }

                    # Only add image data if it exists
                    if product_data.get("image_1920"):
                        update_data["image_1920"] = product_data.get("image_1920")

                    # Update product if it exists
                    product.write(update_data)
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
                self.env.cr.commit()  # commit after creating a new product

            if products.has_next_page:
                products = products.next_page()
            else:
                products = False
