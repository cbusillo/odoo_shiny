import base64
import logging
import io
import requests
from PIL import Image
from odoo import fields, models, api
from odoo.exceptions import UserError
from ..mixins.product_bin_label import ProductBinLabelMixin

_logger = logging.getLogger(__name__)


class ProductType(models.Model):
    _name = "product.type"
    _description = "Product Type"
    _sql_constraints = [
        ("name_uniq", "unique (name)", "Product Type name already exists !"),
    ]

    name = fields.Char(required=True, index=True)


class ProductImportImage(models.Model):
    _name = "product.import.image"
    _description = "Product Import Image"

    image_data = fields.Image(max_width=1920, max_height=1920)
    product_id = fields.Many2one("product.import", ondelete="cascade")


class ProductImport(models.Model, ProductBinLabelMixin):
    _name = "product.import"
    _description = "Product Import"
    _sql_constraints = [
        ("sku_uniq", "unique (sku)", "SKU already exists !"),
    ]

    sku = fields.Char(string="SKU", required=True, copy=False, index=True, default=lambda self: "New")
    mpn = fields.Char(string="MPN", index=True)
    manufacturer = fields.Many2one("product.manufacturer", index=True)
    manufacturer_barcode = fields.Char(index=True)
    quantity = fields.Integer()
    bin = fields.Char(index=True)
    lot_number = fields.Char(index=True)
    name = fields.Char(index=True)
    description = fields.Char()
    type = fields.Many2one("product.type", index=True)
    weight = fields.Float()
    price = fields.Float()
    cost = fields.Float()
    image_1_url = fields.Char(string="Image 1 URL")
    image_upload = fields.Binary()
    image_ids = fields.One2many("product.import.image", "product_id")
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
    export_to_shopify = fields.Binary()

    def name_get(self):
        result = []
        for record in self:
            name = f"[{record.sku}] {record.name or 'No Name Yet'}"
            result.append((record.id, name))
        return result

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

    @api.onchange("image_upload")
    def _onchange_image_upload(self):

        if self.image_upload:
            image = self.env["product.import.image"].create(
                {
                    "image_data": self.image_upload,
                    "product_id": self.id,
                }
            )
            self.image_ids |= image
            self.image_upload = False

    @api.onchange("sku", "mpn", "condition", "bin")
    def _onchange_product_details(self):
        if self._origin.mpn != self.mpn or self._origin.condition != self.condition:
            existing_products = self.products_from_mpn_condition_new()
            if existing_products:
                existing_products_display = [f"{product['sku']} - {product['bin']}" for product in existing_products]
                raise UserError(f"A product with the same MPN already exists.  Its SKU is/are {existing_products_display}")
        if self._origin.bin != self.bin and self.bin:
            if self._existing_bin() is False:
                self._print_bin_label()
        if self.sku and self.mpn and self.condition:
            self._print_product_label()

    def _products_from_existing_records(self, field_name: str, field_value: str) -> str | None:
        is_new_record = isinstance(self.id, models.NewId)  # pylint: disable=no-member
        if is_new_record:
            product_imports = self.env["product.import"].search([(field_name, "=", field_value)])
        else:
            product_imports = self.env["product.import"].search(
                [(field_name, "=", field_value), ("id", "!=", self.id)]  # pylint: disable=no-member
            )
        product_templates = self.env["product.template"].search([(field_name, "=", field_value)])

        existing_products = {}
        for product in product_imports:
            product_to_add = {"sku": product.sku, "bin": product.bin, "condition": product.condition}
            existing_products[product.sku] = product_to_add

        for product in product_templates:
            product_to_add = {"sku": product.default_code, "bin": product.bin, "condition": product.condition}
            existing_products[product.default_code] = product_to_add

        return list(existing_products.values())

    def products_from_mpn_condition_new(self) -> str:
        if self.mpn and self.condition == "new":
            existing_products = self._products_from_existing_records("mpn", self.mpn)
            existing_new_products = [product for product in existing_products if product["condition"] == "new"]
            if existing_new_products:
                return existing_new_products
        return None

    def _existing_bin(self) -> bool:
        if self.bin:
            existing_products = self._products_from_existing_records("bin", self.bin)
            if existing_products:
                return True
        return False

    def _print_product_label(self):
        label_data = [
            f"SKU: {self.sku}",
            "MPN: ",
            f"(SM){self.mpn}",
            f"Bin: {self.bin or '       '}",
            self.condition.title(),
        ]
        label = self.env["printnode.interface"].generate_label(label_data, self.sku)
        self.env["printnode.interface"].print_label(label)

    def _print_bin_label(self):
        label = self.env["printnode.interface"].generate_label(["", "Bin:", self.bin], self.bin)
        self.env["printnode.interface"].print_label(label)

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
            headers = {  # pylint disable=line-too-long
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
            }
            session = requests.Session()
            session.headers.update(headers)
            response = session.get(url, timeout=10)
            try:
                Image.open(io.BytesIO(response.content))
            except IOError:
                _logger.error("The binary data could not be decoded as an image. URL: %s", url)
                return None
            image_base64 = base64.b64encode(response.content)
        except requests.exceptions.Timeout:
            _logger.error("Timeout Error getting image from SKU: %s, URL: %s", self.sku, url)
            return None
        except requests.exceptions.RequestException:
            _logger.error("Request Error getting image from SKU: %s, URL: %s", self.sku, url)
            return None
        return image_base64

    def import_to_products(self):
        missing_data_records = self.filtered(lambda record: not record.sku or not record.name)
        if missing_data_records:
            _logger.warning("Missing data for records: %s", missing_data_records)

        for record in self - missing_data_records:
            existing_products = record.products_from_mpn_condition_new()
            if existing_products:
                existing_products_display = [f"{product['sku']} - {product['bin']}" for product in existing_products]
                raise UserError(f"A product with the same MPN already exists.  Its SKU is/are {existing_products_display}")
            product = self.env["product.product"].search([("default_code", "=", record.sku)], limit=1)
            image_from_url_data = None
            if record.image_1_url:
                image_from_url_data = record.get_image_from_url(record.image_1_url)
                if image_from_url_data is None:
                    _logger.warning("Skipping import of record with SKU: %s due to image error.", record.sku)
                    continue

            product_data = {
                "default_code": record.sku or product.default_code,
                "mpn": record.mpn or product.mpn,
                "manufacturer": record.manufacturer.id or product.manufacturer.id,
                "bin": record.bin or product.bin,
                "name": record.name or product.name,
                "description_sale": record.description or product.description_sale,
                "part_type": record.type.id or product.part_type.id,
                "weight": record.weight if record.weight > 0 else product.weight,
                "list_price": record.price if record.price > 0 else product.list_price,
                "standard_price": record.cost if record.cost > 0 else product.standard_price,
                "condition": record.condition or product.condition,
                "detailed_type": "product",
                "is_published": True,
                "shopify_next_export": True,
                "manufacturer_barcode": record.manufacturer_barcode or product.manufacturer_barcode,
                "lot_number": record.lot_number or product.lot_number,
            }

            if product:
                product.write(product_data)
            else:
                product = self.env["product.product"].create(product_data)
            if record.quantity > 0:
                product.update_quantity(record.quantity)

            current_images = self.env["product.image"].search([("product_tmpl_id", "=", product.product_tmpl_id.id)])
            current_index = 1
            for image in current_images:
                if int(image.name or 0) > current_index:
                    current_index = int(image.name or 1)

            if image_from_url_data:
                self.env["product.image"].create(
                    {
                        "image_1920": image_from_url_data,
                        "product_tmpl_id": product.product_tmpl_id.id,
                        "name": current_index,
                    }
                )
                current_index += 1

            for image in record.image_ids:
                self.env["product.image"].create(
                    {
                        "image_1920": image.image_data,
                        "product_tmpl_id": product.product_tmpl_id.id,
                        "name": current_index,
                    }
                )
                current_index += 1
            record.unlink()
        return {"type": "ir.actions.client", "tag": "reload"}

    def open_product_import_wizard(self):
        return {
            "name": "Calculate Costs",
            "type": "ir.actions.act_window",
            "res_model": "product.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_selected_product_ids": self.ids},
        }
