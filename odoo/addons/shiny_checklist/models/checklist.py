from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class Tech(models.Model):
    _name = "shiny_checklist.tech"
    _description = "Name of the tech testing the device."

    user_id = fields.Many2one("res.users", string="Technician", required=True)


class Test(models.Model):
    _name = "shiny_checklist.test"
    _order = "sort_order"
    _description = "A test that can be performed on a device."

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    sort_order = fields.Integer(default=0)


class Spec(models.Model):
    _name = "shiny_checklist.spec"
    _order = "sort_order"
    _description = "A spec that can be on a device."

    name = fields.Char(required=True)
    sort_order = fields.Integer(default=0)


class SpecOption(models.Model):
    _name = "shiny_checklist.spec_option"
    _description = "Option for a spec result."

    name = fields.Char(required=True)
    spec_ids = fields.Many2many("shiny_checklist.spec", string="Specs")
    device_type_ids = fields.Many2many("shiny_checklist.device_type", string="Device Types")
    checklist_id = fields.Many2one("shiny_checklist.checklist", string="Checklist", ondelete="cascade")


class DeviceType(models.Model):
    _name = "shiny_checklist.device_type"
    _description = "Type of device, for example MacBook or iPhone."

    name = fields.Char(required=True)


class DevicePart(models.Model):
    _name = "shiny_checklist.device_part"
    _description = "Part of a device, for example screen or keyboard or complete unit."

    name = fields.Char(required=True)


class Device(models.Model):
    _name = "shiny_checklist.device"
    _description = (
        "A device that can be tested.  Combination of type and part.  Includes all the possible tests and spec for the device."
    )

    device_type_id = fields.Many2one("shiny_checklist.device_type", required=True)
    device_part_id = fields.Many2one("shiny_checklist.device_part", required=True)
    spec_ids = fields.Many2many("shiny_checklist.spec", "device_spec_rel", "device_id", "spec_id")
    test_ids = fields.Many2many("shiny_checklist.test", "device_test_rel", "device_id", "test_id")


class TestResult(models.Model):
    _name = "shiny_checklist.test_result"
    _description = "Result of a test performed on a device."

    test_id = fields.Many2one("shiny_checklist.test", string="Test", required=True)
    checklist_id = fields.Many2one("shiny_checklist.checklist", string="Checklist", required=True, ondelete="cascade")
    test_result = fields.Selection(
        [("P", "Pass"), ("F", "Fail"), ("O", "Other"), ("NA", "Not Applicable"), ("NT", "Not Tested")],
        default="NT",
    )
    test_comment = fields.Text()
    device_ids = fields.Many2many("shiny_checklist.device", string="Devices", compute="_compute_devices")

    @api.depends("device_ids")
    def _compute_devices(self):
        for test in self:
            test.device_ids = self.env["shiny_checklist.device"].search([("test_ids", "in", test.test_id.id)])


class SpecResult(models.Model):
    _name = "shiny_checklist.spec_result"
    _description = "Result of a spec performed on a device."

    spec_id = fields.Many2one("shiny_checklist.spec", string="Spec", required=True)
    checklist_id = fields.Many2one("shiny_checklist.checklist", string="Checklist", required=True, ondelete="cascade")
    device_type_id = fields.Many2one(related="checklist_id.device_type_id")
    spec_option_id = fields.Many2one("shiny_checklist.spec_option", string="Spec Option")

    device_ids = fields.Many2many("shiny_checklist.device", string="Devices", compute="_compute_devices")

    @api.depends("device_ids")
    def _compute_devices(self):
        for spec in self:
            spec.device_ids = self.env["shiny_checklist.device"].search([("spec_ids", "in", spec.spec_id.id)])


class Checklist(models.Model):
    _name = "shiny_checklist.checklist"
    _description = "A checklist for a device."

    device_type_id = fields.Many2one("shiny_checklist.device_type", required=True)
    device_part_id = fields.Many2one("shiny_checklist.device_part", required=True)
    tech_id = fields.Many2one("shiny_checklist.tech", required=True)
    date = fields.Date(default=fields.Date.today, required=True)
    serial_number = fields.Char(required=False)
    test_result_ids = fields.One2many("shiny_checklist.test_result", "checklist_id", string="Test Results")
    spec_option_ids = fields.One2many("shiny_checklist.spec_option", "checklist_id", string="Spec Options")
    spec_result_ids = fields.One2many("shiny_checklist.spec_result", "checklist_id", string="Spec Results")
    test_ids = fields.Many2many(
        "shiny_checklist.test",
        string="Tests",
        compute="_compute_tests_specs",
        store=True,
    )
    spec_ids = fields.Many2many(
        "shiny_checklist.spec",
        string="Specs",
        compute="_compute_tests_specs",
        store=True,
    )

    @api.depends("serial_number", "date")
    def name_get(self):
        result = []
        for checklist in self:
            name = f"{checklist.serial_number} {checklist.date}" or "New"
            result.append((checklist.id, name))
        return result

    @api.depends("device_type_id", "device_part_id")
    def _compute_serial_number(self):
        for checklist in self:
            if checklist.device_type_id and checklist.device_part_id:
                checklist.serial_number = f"{checklist.device_type_id.name} - {checklist.device_part_id.name}"
            else:
                checklist.serial_number = ""

    @api.onchange("device_type_id", "device_part_id")
    def _onchange_device_type_part(self):
        self.spec_result_ids = [(5,)]  # Clear existing spec options
        self.test_result_ids = [(5,)]  # Clear existing test results
        if self.device_type_id and self.device_part_id:
            device = self.env["shiny_checklist.device"].search(
                [
                    ("device_type_id", "=", self.device_type_id.id),
                    ("device_part_id", "=", self.device_part_id.id),
                ],
                limit=1,
            )
            spec_results = []
            for spec in device.spec_ids:
                spec_results.append((0, 0, {"spec_id": spec.id}))
            self.spec_result_ids = spec_results

            test_results = []
            for test in device.test_ids:
                test_results.append((0, 0, {"test_id": test.id}))
            self.test_result_ids = test_results
