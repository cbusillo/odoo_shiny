import base64
import datetime
import textwrap
import os

from printnodeapi import Gateway
from simple_zpl2 import ZPLDocument, Code128_Barcode
from odoo import models, api, fields, _
from odoo.exceptions import UserError

LABEL_SIZE = {"width": 2, "height": 1.3}
LABEL_TEXT_SIZE = {"width": 40, "height": 40, "small_width": 20, "small_height": 20}
LABEL_PADDING = 10
BARCODE_HEIGHT = 35


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
    def print_label(self, label_data):
        gateway = self.get_gateway()
        user_printer = self.env["printnode.interface"].search([("user_id", "=", self.env.user.id)], limit=1)
        if user_printer:
            printer_id = user_printer.printer_selection
            label = self.generate_label(text=label_data, barcode="1234", quantity=1)
            zpl_commands = "^XA^FO50,50^A0N,50,50^FDHello, World!^FS^XZ"
            label_base64 = base64.b64encode(zpl_commands.encode("utf-8")).decode("utf-8")
            print_job = gateway.PrintJob(
                printer=int(printer_id),
                job_type="raw",
                title="Odoo Product Label",
                options={"copies": 1},
                base64=label_base64,
            )
            return print_job
        raise UserError(_("No printer selected"))

    @api.model
    def _setup_complete(self):
        super(PrintNodeInterface, self)._setup_complete()
        label_data = "test"
        # self.print_label(label_data)
        return

    def generate_label(
        self,
        text: list[str] | str,
        barcode: str | None = None,
        text_bottom: str | None = None,
        quantity: int = 1,
        print_date: bool = True,
    ):
        """Open socket to printer and send text"""

        if not isinstance(text, list):
            text = [text]

        text = self.wrap_list_text(text, 20)

        label_width = int(203 * LABEL_SIZE["width"])
        label_height = int(203 * LABEL_SIZE["height"])

        quantity = max(int(quantity), 1)
        label = ZPLDocument()
        label.add_zpl_raw("^BY2")
        label.add_default_font(font_name=0, character_height=LABEL_TEXT_SIZE["height"], character_width=LABEL_TEXT_SIZE["width"])
        current_origin = LABEL_PADDING
        for index, line in enumerate(text):
            label.add_field_block(text_justification="C", width=label_width)
            label.add_field_origin(x_pos=LABEL_PADDING, y_pos=current_origin, justification=2)
            label.add_field_data(line)
            current_origin = (index + 1) * LABEL_TEXT_SIZE["height"] + LABEL_PADDING

        if print_date:
            today = datetime.date.today()
            formatted_date = f"{today.month}.{today.day}.{today.year}"
            label.add_default_font(
                font_name=0, character_height=LABEL_TEXT_SIZE["small_height"], character_width=LABEL_TEXT_SIZE["small_width"]
            )
            label.add_field_block(text_justification="C", width=label_width)
            label.add_field_origin(x_pos=LABEL_PADDING, y_pos=current_origin, justification=2)
            label.add_field_data(formatted_date)
            current_origin = current_origin + (LABEL_TEXT_SIZE["small_height"])

        if text_bottom:
            label.add_field_block(text_justification="C", width=label_width)
            label.add_field_origin(x_pos=LABEL_PADDING, y_pos=current_origin, justification=2)
            label.add_field_data(text_bottom)

        current_origin = int(label_height - (BARCODE_HEIGHT * 2))

        if barcode:
            centered_left = 194 - int(((len(barcode) * 21) + 75) / 2)
            barcode_zpl = Code128_Barcode(barcode, "N", BARCODE_HEIGHT, "Y", "N")

            label.add_field_block(width=label_width)
            label.add_field_origin(x_pos=LABEL_PADDING + centered_left, y_pos=current_origin, justification=2)
            label.add_barcode(barcode_zpl)
            current_origin = current_origin + int(BARCODE_HEIGHT / 9) + 2

        return label.zpl_text

    def wrap_list_text(self, text: list[str], length: int) -> list[str]:
        """take a list of text and return wrapped lines of length"""
        wrapped_text = []
        for line in text:
            if len(line) <= length:
                wrapped_text.append(line)
                continue
            wrapped_lines = textwrap.wrap(line, 20, break_long_words=True, break_on_hyphens=True, replace_whitespace=False)
            for wrapped_line in wrapped_lines:
                wrapped_text.append(wrapped_line)
        return wrapped_text
