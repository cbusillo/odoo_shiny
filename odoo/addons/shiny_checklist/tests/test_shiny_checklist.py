from odoo.tests.common import TransactionCase


class TestShinyChecklist(TransactionCase):
    def setUp(self):
        super().setUp()

        self.Technician = self.env["shiny_checklist.technician"]
        self.Test = self.env["shiny_checklist.test"]
        self.Specification = self.env["shiny_checklist.specification"]
        self.DeviceType = self.env["shiny_checklist.device_type"]
        self.DevicePart = self.env["shiny_checklist.device_part"]
        self.Device = self.env["shiny_checklist.device"]
        self.TestResult = self.env["shiny_checklist.test_result"]
        self.SpecificationResult = self.env["shiny_checklist.specification_result"]
        self.Checklist = self.env["shiny_checklist.checklist"]

    def test_create_technician(self):
        technician = self.Technician.create({"name": "John Doe"})
        self.assertEqual(technician.name, "John Doe")

    def test_create_test(self):
        test = self.Test.create({"name": "Test 1", "code": "T1"})
        self.assertEqual(test.name, "Test 1")
        self.assertEqual(test.code, "T1")

    # Add more test methods for other models

    def test_create_checklist(self):
        technician = self.Technician.create({"name": "John Doe"})
        device_type = self.DeviceType.create({"name": "MacBook"})
        device_part = self.DevicePart.create({"name": "Screen"})

        checklist = self.Checklist.create(
            {
                "device_type_id": device_type.id,
                "device_part_id": device_part.id,
                "technician_id": technician.id,
                "date": "2023-05-30",
                "serial_number": "1234567890",
            }
        )

        self.assertEqual(checklist.device_type_id, device_type)
        self.assertEqual(checklist.device_part_id, device_part)
        self.assertEqual(checklist.technician_id, technician)
        self.assertEqual(checklist.date, "2023-05-31")
        self.assertEqual(checklist.serial_number, "1234567890")
