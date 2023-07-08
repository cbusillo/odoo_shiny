import base64
import datetime
import os

from printnodeapi import Gateway
from simple_zpl2 import ZPLDocument
from odoo import models, api, fields, _
from odoo.exceptions import UserError


class PrintNodeInterface(models.Model):
    _name = "printnode.interface"
    _description = "PrintNode Interface"
    _sql_constraints = [
        ("user_id_print_job_type_unique", "unique(user_id, print_job_type)", "Printer already selected for this job type and user")
    ]

    printer_selection = fields.Selection(selection="get_printers", string="Printer")
    print_job_type = fields.Selection(
        selection=[("product_import_label", "Product Import Label"), ("receipt", "Receipt")], default="product_import_label"
    )
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user)

    LABEL_SIZE = {"width": 1, "height": 1.3}
    LABEL_TEXT_SIZE = {"large": 60, "medium": 40, "small": 20}
    LABEL_PADDING_Y = 10
    LABEL_PADDING_X = 220
    BARCODE_HEIGHT = 35

    def get_gateway(self):
        api_key = os.environ.get("PRINTNODE_API_KEY")
        if not api_key:
            raise UserError(_("No PrintNode API key found"))
        return Gateway(apikey=api_key)

    def get_printers(self):
        gateway = self.get_gateway()
        printers = [(str(printer.id), printer.name) for printer in gateway.printers()]
        if not printers:
            raise UserError(_("No printers found on PrintNode"))
        return printers

    @api.model
    def print_label(self, label: base64, quantity: int = 1):
        gateway = self.get_gateway()
        user = self.env["printnode.interface"].search([("user_id", "=", self.env.user.id)], limit=1)
        if not user:
            return False
        printer = user.printer_selection
        if not printer:
            return False

        print_job = gateway.PrintJob(
            printer=int(printer),
            job_type="raw",
            title="Odoo Product Label",
            options={"copies": quantity},
            base64=label,
        )
        return print_job

    def generate_label(
        self,
        text: list[str] | str,
        barcode: str | None = None,
        quantity: int = 1,
        print_date: bool = True,
    ) -> base64:
        """Open socket to printer and send text"""

        if not isinstance(text, list):
            text = [text]

        label_width = int(203 * self.LABEL_SIZE["width"])
        label_text_size = self.LABEL_TEXT_SIZE["large"] if text[0] == "" else self.LABEL_TEXT_SIZE["medium"]

        quantity = max(int(quantity), 1)
        label = ZPLDocument()
        label.add_zpl_raw("^BY2")

        current_origin = self.LABEL_PADDING_Y
        for index, line in enumerate(text):
            current_line_text_size = (
                self.LABEL_TEXT_SIZE["small"] if line.startswith("(SM)") and len(line.replace("(SM)", "")) > 8 else label_text_size
            )
            line = line.replace("(SM)", "")
            label.add_default_font(font_name=0, character_height=current_line_text_size, character_width=current_line_text_size)
            label.add_field_block(text_justification="C", width=label_width)
            label.add_field_origin(x_pos=self.LABEL_PADDING_X, y_pos=current_origin, justification=2)
            label.add_field_data(line)
            current_origin = (index + 1) * label_text_size + self.LABEL_PADDING_Y

        if print_date:
            today = datetime.date.today()
            formatted_date = f"{today.month}.{today.day}.{today.year}"
            label.add_default_font(
                font_name=0,
                character_height=self.LABEL_TEXT_SIZE["small"],
                character_width=self.LABEL_TEXT_SIZE["small"],
            )
            label.add_field_block(text_justification="C", width=label_width)
            label.add_field_origin(x_pos=self.LABEL_PADDING_X, y_pos=current_origin, justification=2)
            label.add_field_data(formatted_date)
            current_origin = current_origin + (self.LABEL_TEXT_SIZE["small"])

        if barcode:
            label.add_field_origin(x_pos=10, y_pos=10, justification=2)
            barcode_size = 10
            label.add_zpl_raw(f"^BQN,2,{barcode_size}^FDQAH," + barcode + "^FS^XZ")
        return base64.b64encode(label.zpl_text.encode("utf-8")).decode("utf-8")
