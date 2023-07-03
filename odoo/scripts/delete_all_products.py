import xmlrpc.client

URL = "http://localhost:8069"
DB = "odoo_shiny"
USERNAME = "admin"
PASSWORD = "admin"

model_names = [
    "stock.picking",
    "stock.move",
    "stock.quant",
    "product.template",
    "product.product",
]

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USERNAME, PASSWORD, {})

models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

for model_name in model_names:
    object_ids = models.execute_kw(DB, uid, PASSWORD, model_name, "search", [[]])

    models.execute_kw(DB, uid, PASSWORD, model_name, "unlink", [object_ids])
