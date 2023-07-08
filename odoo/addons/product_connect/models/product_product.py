from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = "product.product"
    _sql_constraints = [
        ("default_code_uniq", "unique (default_code)", "SKU already exists !"),
    ]

    shopify_product_id = fields.Char(copy=False)
    shopify_last_exported = fields.Datetime(string="Last Exported Time")
    shopify_next_export = fields.Boolean(string="Export Next Sync?")

    def update_quantity(self, quantity):
        stock_location = self.env.ref("stock.stock_location_stock")
        for product in self:
            quant = self.env["stock.quant"].search(
                [("product_id", "=", product.id), ("location_id", "=", stock_location.id)], limit=1
            )

            if not quant:
                quant = self.env["stock.quant"].create({"product_id": product.id, "location_id": stock_location.id})

            quant.with_context(inventory_mode=True).write({"quantity": float(quantity)})
