import base64
import logging
import requests
from odoo import fields, models, api

_logger = logging.getLogger(__name__)


class ProductType(models.Model):
    _name = "product.type"
    _description = "Product Type"
    _sql_constraints = [
        ("name_uniq", "unique (name)", "Product Type name already exists !"),
    ]

    name = fields.Char(required=True, index=True)


class ProductImport(models.Model):
    _name = "product.import"
    _description = "Product Import"
    _sql_constraints = [
        ("sku_uniq", "unique (sku)", "SKU already exists !"),
    ]

    sku = fields.Char(string="SKU", required=True, copy=False, index=True, default=lambda self: "New")
    mpn = fields.Char(string="MPN", index=True)
    manufacturer = fields.Many2one("product.manufacturer", index=True)
    quantity = fields.Integer()
    bin = fields.Char(index=True)
    name = fields.Char(index=True)
    description = fields.Char()
    type = fields.Many2one("product.type", index=True)
    weight = fields.Float()
    price = fields.Float()
    cost = fields.Float()
    pic_1_url = fields.Char()
    pic_1_bytes = fields.Image(max_width=1920, max_height=1920)
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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("sku", "") == "New" or not vals.get("sku"):
                vals["sku"] = self.env["ir.sequence"].next_by_code("product.import")
            if vals.get("mpn"):
                vals["mpn"] = vals["mpn"].upper()
            if vals.get("bin"):
                vals["bin"] = vals["bin"].upper()
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("mpn"):
            vals["mpn"] = vals["mpn"].upper()
        if vals.get("bin"):
            vals["bin"] = vals["bin"].upper()
        return super().write(vals)

    @api.model
    def load(self, fields, data):  # pylint: disable=redefined-outer-name
        for row in data:
            if "mpn" in fields:
                idx = fields.index("mpn")
                row[idx] = row[idx].upper()
            if "bin" in fields:
                idx = fields.index("bin")
                row[idx] = row[idx].upper()
        return super(ProductImport, self).load(fields, data)

    def open_record(self):
        self.ensure_one()
        return {  # pylint: disable=no-member
            "type": "ir.actions.act_window",
            "res_model": "product.import",
            "view_mode": "form",
            "res_id": self.id,
        }

    def get_image_from_url(self, url: str) -> bytes | None:
        if not url:
            return False
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            image_base64 = base64.b64encode(response.content)
        except requests.exceptions.RequestException as error:
            _logger.warning("Error getting image from URL %s: %s", url, error)
            return False
        return image_base64

    def import_to_products(self):
        missing_data_records = self.filtered(lambda record: not record.sku or not record.name)
        if missing_data_records:
            _logger.warning("Missing data for records: %s", missing_data_records)

        for record in self - missing_data_records:
            if record.name is None:
                continue
            product_data = {
                "default_code": record.sku,
                "mpn": record.mpn,
                "manufacturer": record.manufacturer.id,
                "bin": record.bin,
                "name": record.name,
                "description_sale": record.description,
                "part_type": record.type.id,
                "weight": record.weight,
                "list_price": record.price,
                "standard_price": record.cost,
                "detailed_type": "product",
                "is_published": True,
                "image_1920": self.get_image_from_url(record.pic_1_url),
                "condition": record.condition,
            }
            product = self.env["product.product"].search([("default_code", "=", record.sku)], limit=1)
            if product:
                product.write(product_data)
            else:
                product = self.env["product.product"].create(product_data)
            product.update_quantity(record.quantity)
            record.unlink()
        return {"type": "ir.actions.client", "tag": "reload"}
