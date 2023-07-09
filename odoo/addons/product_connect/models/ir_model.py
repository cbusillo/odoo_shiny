from odoo import models


class IrModel(models.Model):
    _inherit = "ir.model"

    def fill_down(self, model_name, active_field, selected_records, active_record_id):
        model = self.env[model_name]
        active_record = model.browse(active_record_id)
        records = model.browse(selected_records)
        value = active_record[active_field]
        records.write({active_field: value})
