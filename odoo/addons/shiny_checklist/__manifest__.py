# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring, manifest-required-author, missing-readme
{
    "name": "shiny_checklist",
    "version": "16.0.0.0.3",
    "summary": "Checklist app",
    "category": "Industries",
    "author": "Chris Busillo",
    "company": "Shiny Computers",
    "website": "https://www.shinycomputers.com",
    "depends": ["base"],
    "data": [
        "data/default.xml",
        "views/shiny_checklist_views.xml",
        "security/ir.model.access.csv",
    ],
    "images": ["static/description/icon.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
    "license": "LGPL-3",
}
