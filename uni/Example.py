"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

from .University import University
import logging
import pymongo

# Replace Uni Name with abbreviated name of university
log = logging.getLogger("Uni Name")

class Example(University):
    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm

    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """
        log.info("Obtain course info here!")