# -*- coding: utf-8 -*-
# pylint: disable=missing-docstring, manifest-required-author, missing-readme,
# pyright: reportUnusedExpression=false
{
    "name": "Scraping Module",
    "version": "1.0",
    "category": "Industries",
    "author": "Chris Busillo",
    "company": "Shiny Computers",
    "website": "https://www.shinycomputers.com",
    "depends": ["base"],
    "description": "Module to scrape websites for model data.",
    "data": [
        "security/ir.model.access.csv",
        "views/product_scraper_views.xml",
    ],
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}
