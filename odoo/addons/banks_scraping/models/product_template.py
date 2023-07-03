from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bin = fields.Char(index=True)
    mpn = fields.Char(string="MPN", index=True)
    manufacturer = fields.Many2one("product.manufacturer", index=True)
    part_type = fields.Many2one("product.type", index=True)
    product_images = fields.One2many("product.images.extension", "product_id")

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
