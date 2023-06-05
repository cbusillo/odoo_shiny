from odoo import models, fields, api


class LabelGroup(models.Model):
    _name = "shiny_label.label_group"
    _order = "sort_order"
    _description = "A group of labels that can be printed."

    name = fields.Char(required=True)
    sort_order = fields.Integer(default=0)
    label_ids = fields.Many2many("shiny_label.label", string="Labels")
    printer_ip = fields.Char(required=True)


class Label(models.Model):
    _name = "shiny_label.label"
    _order = "sort_order"
    _description = "A label that can be printed."
    _sql_constraints = [
        ("name_unique", "unique(name)", "Label name must be unique"),
    ]

    name = fields.Char(required=True)
    sort_order = fields.Integer(default=0)


class Printer(models.TransientModel):
    _name = "shiny_label.printer"
    _description = "Print Labels"

    label_id = fields.Many2one("shiny_label.label", string="Label")
    quantity = fields.Integer(default=1)
    custom_text = fields.Char()

    def print_button(self):
        self.ensure_one()
        label_id = self.label_id.id
        quantity = self.quantity
        custom_text = self.custom_text
        self.env["shiny_label.printer"].print_labels(label_id, quantity, custom_text)

    def print_labels(self, label_id, quantity, custom_text):
        print(f"Printing {quantity} labels with id {label_id} and custom text {custom_text}")
