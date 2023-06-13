from odoo import models, fields, api
import shopify
import binascii
import os
from string import capwords
import re
from urllib.parse import urlparse
import base64

from bs4 import BeautifulSoup
import requests
from requests.exceptions import RequestException
from tenacity import retry, stop_after_attempt, wait_fixed

BASE_URL = "https://www.crowleymarine.com"


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

    source_url = fields.Char()
    source_url_display = fields.Char(compute="_compute_source_url_display")
    product_id = fields.Many2one("product.scraper", string="Related Product")

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
    url = fields.Char(string="URL")
    url_display = fields.Char(compute="_compute_url_display", string="Path")
    sku = fields.Char(required=True, string="SKU")
    price = fields.Float()
    brand = fields.Char()

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
            return "<th style='border:1px solid black; padding:10px;'>{}</th>".format(header)

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
        header_row = "<tr>{}</tr>".format("".join(format_header(header) for header in headers))

        for record in self:
            urls = (url.source_url_display for url in record.source_url_ids)

            table_rows = []
            for url in urls:
                cells = url.split("/")[1:]  # Skip the first cell if it's blank
                formatted_cells = [format_cell(index, cell, len(cells)) for index, cell in enumerate(cells)]
                table_rows.append(
                    "<tr>{}</tr>".format(
                        "".join("<td style='border:1px solid black; padding:10px;'>{}</td>".format(cell) for cell in formatted_cells)
                    )
                )

            record.source_url_html = "<table style='border:1px solid black'>{}</table>".format(header_row + "".join(table_rows))

    @api.model
    def scrape_website(self):
        visited_urls = set()
        visited_end_links = {}

        @retry(stop=stop_after_attempt(5), wait=wait_fixed(1))
        def get(url):
            response = requests.get(url)
            if response.status_code != 404:  # Only raise if status code is not 404
                response.raise_for_status()  # Raises a HTTPError if one occurred
            return response

        def get_links_in_page(url: str, search_regex: str = r"/((19|20)\d{2}|ag|af|ab|aa)") -> list:
            if BASE_URL not in url:
                url = BASE_URL + url.replace("file://", "")

            if url in visited_urls and url != BASE_URL:
                print(f"Already visited: {url}")
                return []

            print(f"Visiting: {url}")
            try:
                response = get(url)
            except requests.exceptions.HTTPError as e:
                print(f"Error during requests to {url} : {str(e)}")
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
            if "oem-parts" not in main_link:
                continue
            for type_year_link in get_links_in_page_year(main_link):
                if "outboard" not in type_year_link:
                    continue
                for motor_link in get_links_in_page_year(type_year_link):
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
                                except requests.exceptions.HTTPError as e:
                                    print(f"Error during requests to {end_link} : {str(e)}")
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
                                print(f"Checking product: {product_data}")
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
                                print(f"Updated product: {product_data}")
                            else:
                                # Create product if it does not exist
                                product = self.create(product_data)
                                print(f"Created new product: {product_data}")
                                self.env.cr.commit()  # commit after creating a new product

                            # Check if source_url already exists for the product
                            source_exists = self.env["product.scraper.source"].search(
                                [("source_url", "=", part_link), ("product_id", "=", product.id)], limit=1
                            )

                            if not source_exists:
                                # Add source_url to product
                                source = self.env["product.scraper.source"].create(
                                    {
                                        "source_url": part_link,
                                        "product_id": product.id,
                                    }
                                )
                                print(f"Added source URL {part_link} to product {product.name}")
                                self.env.cr.commit()  # commit after creating a new source URL
                            else:
                                print(f"Source URL {part_link} already exists for product {product.name}")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def sync_shopify_products(self):
        # Setup Shopify API
        shop_url = "yps-your-part-supplier"
        api_version = "2023-01"
        api_key = os.environ.get("SHOPIFY_API_KEY")
        password = os.environ.get("SHOPIFY_API_SECRET_KEY")
        token = os.environ.get("SHOPIFY_API_TOKEN")

        shopify.Session.setup(api_key=api_key, secret=token)

        shopify.ShopifyResource.set_site(f"https://{api_key}:{token}@{shop_url}.myshopify.com/admin")

        # Retrieve all products from Shopify
        products = shopify.Product.find()

        # Loop over all products
        for shopify_product in products:
            # Extract required data
            product_data = {
                "name": shopify_product.title,
                "barcode": shopify_product.variants[0].sku if shopify_product.variants else None,
                "list_price": float(shopify_product.variants[0].price) if shopify_product.variants else 0.0,
                "default_code": f"https://{shop_url}.myshopify.com/products/{shopify_product.handle}",
                # "brand": "Shopify",  # Set a default brand, replace this with real data if available
            }

            # Get main image and encode it to base64
            if shopify_product.images:
                response = requests.get(shopify_product.images[0].src)
                image_base64 = base64.b64encode(response.content)
                product_data["image_1920"] = image_base64

            # Search for existing product
            product = self.search([("default_code", "=", product_data["default_code"])], limit=1)

            if product:
                # Update product if it exists
                product.write(
                    {
                        "name": product_data["name"],
                        "list_price": product_data["list_price"],
                        "default_code": product_data["default_code"],
                        "barcode": product_data["barcode"],
                        "image_1920": product_data["image_1920"],
                    }
                )
            else:
                # Create product if it does not exist
                product = self.create(product_data)
                self.env.cr.commit()  # commit after creating a new product
