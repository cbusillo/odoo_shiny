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
