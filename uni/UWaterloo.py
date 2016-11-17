"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

from .University import University
from uwaterlooapi import UWaterlooAPI
import logging
import time
import pymongo

log = logging.getLogger("UWaterloo")


class UWaterloo(University):
    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm

    def updateFaculties(self, uw):
        log.info("Getting faculty list")
        faculties = uw.group_codes

        for subject in uw.subject_codes():
            subjectdict = {'subject': subject['subject'], 'faculty': '', 'name': subject['description']}
            for faculty in faculties:
                if subject['group'] == faculty['group_code']:
                    subjectdict[faculty] = faculty['group_full_name']
            self.updateSubject(subjectdict)

    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """

        if self.settings['scrape']:
            while True:
                try:
                    uw = UWaterlooAPI(api_key="d4b5c3ce7b33a28074b86ab0bcf2d2c9")
                    #print(dir(uw))

                    self.updateFaculties(uw)
                except Exception as e:
                    log.info("There was a critical exception | " + str(e))
                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            log.info("Scraping is disabled")