import re
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class ProductTemplate(models.Model):
    _inherit = "product.template"

    bin = fields.Char(index=True)
    mpn = fields.Char(string="MPN", index=True)
    manufacturer = fields.Many2one("product.manufacturer", index=True)
    part_type = fields.Many2one("product.type", index=True)
    condition = fields.Selection(
        [
            ("used", "Used"),
            ("new", "New"),
            ("open_box", "Open Box"),
            ("broken", "Broken"),
            ("refurbished", "Refurbished"),
        ],
        default="used",
    )
    # Override fields:
    default_code = fields.Char("SKU", index=True, required=False)
    # product_template_image_ids = fields.One2many("product.image", "product_tmpl_id", string="Product Images")
    image_1920 = fields.Image(compute="_compute_image_1920", inverse="_inverse_image_1920", store=True)

    product_scraper_id = fields.Many2one(
        "product.scraper", compute="_compute_product_scraper_id", store=True, readonly=False, string="Product Scraper"
    )
    product_scraper_html = fields.Text(related="product_scraper_id.source_url_html", string="Product Scraper HTML", readonly=True)
    combined_description = fields.Html(compute="_compute_combined_description", readonly=False)
    shopify_product_id = fields.Char(
        related="product_variant_ids.shopify_product_id", string="Shopify Product ID", readonly=True, store=True
    )

    @api.depends("description_sale", "product_scraper_html")
    def _compute_combined_description(self):
        for record in self:
            record.combined_description = f"{record.description_sale or ''} {record.product_scraper_html or ''}"

    @api.depends("mpn")
    def _compute_product_scraper_id(self):
        for record in self:
            mpn = (record.mpn or "").split(" ")[0]
            if mpn:
                product_scraper = self.env["product.scraper"].search([("sku", "=", mpn)], limit=1)
                record.product_scraper_id = product_scraper

    @api.constrains("default_code")
    def _check_default_code(self):
        for record in self:
            if not re.match(r"^\d{4,8}$", record.default_code):
                raise ValidationError(_("SKU must be 4-8 digits"))

    @api.depends("product_template_image_ids")
    def _compute_image_1920(self):
        for record in self:
            if record.product_template_image_ids:
                record.image_1920 = record.product_template_image_ids[0].image_1920
            else:
                record.image_1920 = False

    def _inverse_image_1920(self):
        for record in self:
            if record.product_template_image_ids:
                record.product_template_image_ids[0].write({"image_1920": record.image_1920})
            elif record.image_1920:
                self.env["product.image"].create({"product_tmpl_id": record.id, "image_1920": record.image_1920})
