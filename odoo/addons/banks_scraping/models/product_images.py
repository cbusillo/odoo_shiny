import base64
from odoo import api, fields, models, tools


class ProductImages(models.Model):
    _name = "product.images"
    _description = "Product Images"

    image_1920 = fields.Image(max_width=1920, max_height=1920, string="XLarge Image")
    image_1024 = fields.Image(compute="_compute_resized_images", store=True, readonly=True, string="Large Image")
    image_512 = fields.Image(compute="_compute_resized_images", store=True, readonly=True, string="Medium Image")
    image_256 = fields.Image(compute="_compute_resized_images", store=True, readonly=True, string="Small Image")
    image_128 = fields.Image(compute="_compute_resized_images", store=True, readonly=True, string="XSmall Image")

    product_id = fields.Many2one("product.template", required=True, ondelete="cascade", index=True)

    @api.depends("image_1920")
    def _compute_resized_images(self):
        for record in self:
            if record.image_1920:
                image_1920_base64 = base64.b64decode(record.image_1920)
                record.image_1024 = base64.b64encode(tools.image_process(image_1920_base64, size=(1024, 1024)))
                record.image_512 = base64.b64encode(tools.image_process(image_1920_base64, size=(512, 512)))
                record.image_256 = base64.b64encode(tools.image_process(image_1920_base64, size=(256, 256)))
                record.image_128 = base64.b64encode(tools.image_process(image_1920_base64, size=(128, 128)))
