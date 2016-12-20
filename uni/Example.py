"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

from .University import University

class Example(University):
    def __init__(self, settings):
        super().__init__(settings)

    def scrape(self):
        """
        Scraping function that obtains updated course info

        :return:
        """
        self.log.info("Obtain course info here!")
