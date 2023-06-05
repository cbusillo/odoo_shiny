from datetime import datetime
import os
import html
from pathlib import Path
import xml.etree.ElementTree as ET
import xmlrpc.client
from xml.dom import minidom

base_path = Path(__file__).resolve().parent / "odoo/addons"
url = "http://localhost:8069"
db = "oodo_shiny"
username = "chris@shinycomputers.com"
password = os.environ.get("ODOO_API_KEY")
modules_model_names = {
    "shiny_label": ["label", "label_group"],
    "shiny_checklist": [
        "device",
        "device_part",
        "device_type",
        "spec",
        "spec_option",
        "test",
    ],
}


def prettify(xml_element):
    rough_string = ET.tostring(xml_element, "utf-8")
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def get_default_data(module_name, model_names):
    common = xmlrpc.client.ServerProxy("{}/xmlrpc/2/common".format(url))
    uid = common.authenticate(db, username, password, {})

    models = xmlrpc.client.ServerProxy("{}/xmlrpc/2/object".format(url))

    xml_root = ET.Element("odoo")
    xml_data = ET.SubElement(xml_root, "data")
    xml_data.set("noupdate", "1")

    for model_name in model_names:
        module_model_name = f"{module_name}.{model_name}"

        fields = models.execute_kw(db, uid, password, module_model_name, "fields_get", [], {"attributes": ["string", "type"]})

        model_data = models.execute_kw(db, uid, password, module_model_name, "search_read", [[]], {"fields": list(fields.keys())})

        for item in model_data:
            xml_record = ET.SubElement(xml_data, "record")
            xml_record.set("id", f"default_{model_name}_{item['id']}")
            xml_record.set("model", module_model_name)

            for key, value in item.items():
                if key in [
                    "__last_update",
                    "create_date",
                    "write_date",
                    "create_uid",
                    "write_uid",
                    "display_name",
                ]:
                    continue

                field_type = fields[key]["type"]

                xml_field = ET.SubElement(xml_record, "field")
                xml_field.set("name", key)

                if field_type in ["many2one"]:
                    if isinstance(value, (list, tuple)):
                        xml_field.set("ref", f"default_{key}_{value[0]}")

                elif field_type in ["many2many", "one2many"]:
                    refs = ", ".join([f"ref('default_{str(key).replace('_ids','')}_{id_}')" for id_ in value])
                    xml_field.set("eval", f"[(6, 0, [{refs}])]")
                else:
                    xml_field.text = html.escape(str(value), quote=True)

    xml_str = prettify(xml_root)

    with open(base_path / module_name / "data/default.xml", "w") as f:
        f.write(xml_str)


if __name__ == "__main__":
    for module, models in modules_model_names.items():
        get_default_data(module, models)
