from odoo import models, fields, api

BASE_URL = "https://www.crowleymarine.com"
START_PAGE = BASE_URL + "/yamaha/oem-parts"


class ProductScraperWizard(models.TransientModel):
    _name = "product.scraper.wizard"
    _description = "Product Scraper Wizard"

    def action_scrape_website(self):
        self.env["product.scraper"].scrape_website()
        return {"type": "ir.actions.act_window_close"}


class ProductScraperSource(models.Model):
    _name = "product.scraper.source"
    _description = "Product Scraper Source URL"

    source_url = fields.Char()
    display_source_url = fields.Char(compute="_compute_display_source_url")
    product_id = fields.Many2one("product.scraper", string="Related Product")

    _sql_constraints = [("product_source_unique", "UNIQUE(source_url, product_id)", "The Source URL must be unique per product!")]

    @api.depends("source_url")
    def _compute_display_source_url(self):
        for record in self:
            record.source_url = record.source_url or ""
            record.display_source_url = record.source_url.replace(START_PAGE, "").replace(BASE_URL, "")


class ProductScraper(models.Model):
    _name = "product.scraper"
    _description = "Product Scraper"

    name = fields.Char()
    source_url_ids = fields.One2many("product.scraper.source", "product_id", string="Source URL Count")
    url = fields.Char()
    display_url = fields.Char(compute="_compute_display_url", string="URL")
    sku = fields.Char(required=True)
    price = fields.Float()

    _sql_constraints = [("sku_unique", "UNIQUE(sku)", "The SKU must be unique!")]

    @api.depends("url")
    def _compute_display_url(self):
        for record in self:
            record.url = record.url or ""
            record.display_url = record.url.replace(START_PAGE, "").replace(BASE_URL, "")

    @api.model
    def scrape_website(self):
        import re
        import os
        from urllib.parse import urlsplit, urljoin, quote

        from seleniumbase import Driver
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import WebDriverException, NoSuchElementException

        LINK_SUBSTRING = "/yamaha/"

        os.system("killall -u cbusillo 'Google Chrome'")

        driver = Driver(headless=False, uc=True)
        driver.implicitly_wait(10)

        visited_urls = set()
        visited_end_links = {}

        def get_element_text_if_exists(css_selector):
            try:
                element = driver.find_element(By.CSS_SELECTOR, css_selector)
                return element.text
            except NoSuchElementException:
                return None

        def get_links_in_page(url: str, search_regex: str = r"/\d{4}") -> list:
            if BASE_URL not in url:
                url = BASE_URL + url.replace("file://", "")

            if url in visited_urls:
                print(f"Already visited: {url}")
                return []

            print(f"Visiting: {url}")
            driver.get(url)
            visited_urls.add(url)

            link_elements = driver.find_elements(By.TAG_NAME, "a")
            links = [
                link.get_attribute("href")
                for link in link_elements
                if link.get_attribute("href") and LINK_SUBSTRING in link.get_attribute("href")
            ]

            filtered_links = [link.split("?")[0].split("#")[0] for link in links if re.search(search_regex, link)]

            return filtered_links

        def get_links_in_page_year(url: str) -> list:
            return get_links_in_page(url)

        def get_links_in_page_product(url: str) -> list:
            return get_links_in_page(url, r"/products/")

        try:
            for model_year_link in get_links_in_page_year(START_PAGE):
                for motor_link in get_links_in_page_year(model_year_link):
                    for part_link in get_links_in_page_year(motor_link):
                        for end_link in get_links_in_page_product(part_link):
                            if end_link in visited_end_links:
                                product_data = visited_end_links[end_link]
                                sku = product_data["sku"]
                            else:
                                driver.get(end_link)

                                sku = get_element_text_if_exists('span[itemprop="sku"]')
                                price = get_element_text_if_exists('span[data-testid="product:price"]')
                                name = get_element_text_if_exists('span[data-testid="product:name"]')

                                product_data = {
                                    "name": name,
                                    "url": end_link,
                                    "sku": sku,
                                    "price": float(price.replace("$", "")) if price else 0.0,
                                }
                                print(f"Checking product: {product_data}")
                                visited_end_links[end_link] = product_data

                            # Search for existing product
                            product = self.search([("sku", "=", sku)], limit=1)

                            if product:
                                # Update product if it exists
                                product.write(
                                    {
                                        "name": name,
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
        except WebDriverException as e:
            print(f"An error occurred while scraping: {str(e)}")
        finally:
            driver.quit()
