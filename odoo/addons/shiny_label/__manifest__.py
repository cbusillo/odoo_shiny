# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring, manifest-required-author, missing-readme
{
    "name": "shiny_label",
    "version": "16.0.0.0.1",
    "summary": "Label printer app",
    "category": "Industries",
    "author": "Chris Busillo",
    "company": "Shiny Computers",
    "website": "https://www.shinycomputers.com",
    "depends": ["base"],
    "data": [
        "views/label_menu.xml",
        "views/label_group_views.xml",
        "views/label_views.xml",
        "security/ir.model.access.csv",
    ],
    "demo": [
        "data/demo.xml",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
