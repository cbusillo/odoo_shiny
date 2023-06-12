from odoo import models, fields, api

BASE_URL = "https://www.crowleymarine.com"


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
    source_url_html = fields.Html(compute="_compute_source_url_html", string="Source URLs HTML")
    url = fields.Char()
    url_display = fields.Char(compute="_compute_url_display", string="URL")
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
                return cell.title().replace("-", " ")
            else:
                return cell.title().replace("Oem-Parts", "OEM")

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
        import re
        import os
        import pickle
        from urllib.parse import urlparse

        from selenium.webdriver import Firefox, FirefoxOptions
        from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import WebDriverException, NoSuchElementException

        options = FirefoxOptions()
        options.set_preference("permissions.default.image", 2)
        options.set_preference("dom.ipc.plugins.enabled.libflashplayer.so", "false")

        options.add_argument("-headless")
        driver = Firefox(options=options)
        driver.implicitly_wait(10)

        # Try loading visited_urls and visited_end_links from file
        try:
            with open(os.path.expanduser("~/.shiny/visited_urls.pkl"), "rb") as f:
                visited_urls = pickle.load(f)
        except FileNotFoundError:
            visited_urls = set()

        try:
            with open(os.path.expanduser("~/.shiny/visited_end_links.pkl"), "rb") as f:
                visited_end_links = pickle.load(f)
        except FileNotFoundError:
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

            if url in visited_urls and url != BASE_URL:
                print(f"Already visited: {url}")
                return []

            print(f"Visiting: {url}")
            driver.get(url)
            visited_urls.add(url)

            # Save visited_urls
            with open(os.path.expanduser("~/.shiny/visited_urls.pkl"), "wb") as f:
                pickle.dump(visited_urls, f)

            link_elements = driver.find_elements(By.TAG_NAME, "a")
            links = [link.get_attribute("href") for link in link_elements if link.get_attribute("href")]

            filtered_links = [link.split("?")[0].split("#")[0] for link in links if re.search(search_regex, link)]

            return filtered_links

        def get_links_in_page_year(url: str) -> list:
            return get_links_in_page(url)

        def get_links_in_page_product(url: str) -> list:
            return get_links_in_page(url, r"/products/")

        def get_links_in_page_main(url: str) -> list:
            return get_links_in_page(url, r"/oem-parts")

        def update_existing():
            # Search for all product scraper records
            products = self.env["product.scraper"].search([])

            # Iterate over each product and update the name
            for product in products:
                if not product.name:
                    continue
                product.write(
                    {
                        "name": product.name.title(),
                        "brand": "Yamaha",
                    }
                )
            self.env.cr.commit()

        # update_existing()
        try:
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
                                brand = urlparse(end_link).path.split("/")[1].title()
                                if end_link in visited_end_links:
                                    product_data = visited_end_links[end_link]
                                    sku = product_data["sku"]
                                else:
                                    driver.get(end_link)

                                    sku = get_element_text_if_exists('span[itemprop="sku"]') or get_element_text_if_exists(
                                        'td[data-testid="product:supersession-item-0-sku"]'
                                    )
                                    price = get_element_text_if_exists('span[data-testid="product:price"]')
                                    if price:
                                        price = price.replace("$", "").replace(",", "")
                                        # Handle price ranges
                                        if "to" in price:
                                            price = [float(p) for p in price.split("to")][0]
                                        else:
                                            price = float(price)
                                    else:
                                        price = 0.0
                                    name = get_element_text_if_exists('span[data-testid="product:name"]')

                                    if not sku or price is None or not name:
                                        sku = sku or ".check-me"
                                    if not name:
                                        name = ""

                                    product_data = {
                                        "name": name.title(),
                                        "url": end_link,
                                        "sku": sku,
                                        "price": price,
                                        "brand": brand,
                                    }
                                    print(f"Checking product: {product_data}")
                                    visited_end_links[end_link] = product_data
                                    with open(os.path.expanduser("~/.shiny/visited_end_links.pkl"), "wb") as f:
                                        pickle.dump(visited_end_links, f)

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
        except WebDriverException as e:
            print(f"An error occurred while scraping: {str(e)}")
        finally:
            driver.quit()
