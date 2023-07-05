import os

from printnodeapi import Gateway

from odoo import models, api, fields


class PrintNodeInterface(models.Model):
    _name = "printnode.interface"
    _description = "PrintNode Interface"

    printer_selection = fields.Selection(selection="get_printers", string="Printer")
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user)

    def get_gateway(self):
        api_key = os.environ.get("PRINTNODE_API_KEY")
        return Gateway(apikey=api_key)

    def get_printers(self):
        gateway = self.get_gateway()
        printers = [(str(printer.id), printer.name) for printer in gateway.printers()]
        return printers

    @api.model
    def print_label(self, printer_id, label_data):
        pass
        # api = printnodeapi.PrintNodeApi(api_key)
        # api.printjob(printer_id, label_data)
