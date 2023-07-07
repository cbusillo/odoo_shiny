from odoo import models


class ProductBinLabelMixin(models.AbstractModel):
    _name = "product.bin.label.mixin"
    _description = "Product Bin Label Mixin"

    def print_bin_labels(self):
        unique_bins = list(set(self.mapped("bin")))
        unique_bins.sort()
        for product_bin in unique_bins:
            label = self.env["printnode.interface"].generate_label(["", "Bin: ", product_bin], product_bin)
            self.env["printnode.interface"].print_label(label)
