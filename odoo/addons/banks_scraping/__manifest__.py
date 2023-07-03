# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring, manifest-required-author, missing-readme, manifest-deprecated-key, manifest-version-format
# pyright: reportUnusedExpression=false
{
    "name": "Scraping Module",
    "version": "16.0.1.0",
    "category": "Industries",
    "author": "Chris Busillo",
    "company": "Shiny Computers",
    "website": "https://www.shinycomputers.com",
    "depends": ["base", "product"],
    "description": "Module to scrape websites for model data.",
    "data": [
        "security/ir.model.access.csv",
        "views/product_import_views.xml",
        "views/product_product_views.xml",
        "views/product_scraper_views.xml",
        "views/product_template_views.xml",
        "views/product_scraper_wizard.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
