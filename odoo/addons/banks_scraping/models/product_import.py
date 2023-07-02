from odoo import fields, models, api


class ProductType(models.Model):
    _name = "product.type"
    _description = "Product Type"
    _sql_constraints = [
        ("name_uniq", "unique (name)", "Product Type name already exists !"),
    ]

    name = fields.Char(required=True)


class ProductManufacturer(models.Model):
    _name = "product.manufacturer"
    _description = "Product Manufacturer"
    _sql_constraints = [
        ("name_uniq", "unique (name)", "Product Type name already exists !"),
    ]

    name = fields.Char(required=True)


class ProductImport(models.Model):
    _name = "product.import"
    _description = "Product Import"
    _sql_constraints = [
        ("sku_uniq", "unique (sku)", "SKU already exists !"),
    ]

    sku = fields.Char(string="SKU", required=True, copy=False, index=True, default=lambda self: "New")
    mpn = fields.Char(string="MPN")
    manufacturer = fields.Many2one("product.manufacturer")
    quantity = fields.Integer()
    bin = fields.Char()
    title = fields.Char()
    description = fields.Char()
    type = fields.Many2one("product.type")
    weight = fields.Float()
    price = fields.Float()
    cost = fields.Float()
    pic_1_url = fields.Char()

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
