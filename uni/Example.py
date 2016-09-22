"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import threading
import pymongo
import time
import logging


log = logging.getLogger("Example")


class Example(threading.Thread):
    def __init__(self, settings):
        threading.Thread.__init__(self)
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm

    def getTerms(self):
        """
        API Handler

        Returns the distinct terms in the database, along with their name and id

        :return: **dict** Keys are the ids, values are the proper names
        """
        termlist = self.db.ExampleCourseList.distinct("term")
        responsedict = {}

        for term in termlist:
            responsedict[str(term)] = self.termIDToName(term)

        return responsedict

    def getLocations(self):
        """
        API Handler

        Returns a list of all locations at UCalgary

        :return: **list** Contains 1D with the possible locations
        """
        locations = self.db.ExampleCourseList.distinct("location")
        response = []

        for location in locations:
            if location != "":
                response.append(location)

        return response

    def getSubjectList(self, term):
        """
        API Handler

        Returns a list of all subjects for a given term

        :param term: **string/int** Term id to retrieve subjects for
        :return: **dict** Contains every subject and course for this term
        """
        responsedict = {}

        return responsedict

    def retrieveCourseDesc(self, courses):
        """
        Given a course list from an API handler, retrieves course descriptions and sorts by faculty

        Pure Function

        :param courses: **dict** List of courses from API handler
        :return: **dict** Faculty sorted dict with course descriptions
        """
        facultydict = {}

        return facultydict

    def getSubjectListAll(self, term):
        """
        API Handler

        Returns all data for a given term (classes, descriptions and RMP)

        :param term: **string/int** ID of the term
        :return: **dict** All data for the term
        """

        # Send over a list of all the professors with a RMP rating in the list
        return {"classes": {}, "rmp": {}}

    def getCourseDescriptions(self):
        """
        API Handler

        Returns the description of every course at UCalgary
        :return: **dict** Description of every course at UCalgary
        """
        responsedict = {}

        # Get the courses
        courses = self.db.ExampleCourseDesc.find()

        for classv in courses:
            # Remove unnecessary fields
            del classv["_id"]
            del classv["lastModified"]

            # If the key for this subject is not in the dict, add it
            if classv["subject"] not in responsedict:
                responsedict[classv["subject"]] = {}

            responsedict[classv["subject"]][classv["coursenum"]] = classv

        return responsedict

    def getSubjectDesc(self):
        """
        API Handler

        Returns the description of every subject at UCalgary

        :return: **dict** Description of every subject at UCalgary
        """
        responsedict = {}
        subjects = self.db.UCalgarySubjects.find()

        for subject in subjects:
            del subject["_id"]
            del subject["lastModified"]

            responsedict[subject["subject"]] = subject
        return responsedict

    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """

        if self.settings["scrape"]:
            while True:
                try:
                    pass
                except Exception as e:
                    log.critical("There was an critical exception | " + str(e))

                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            log.info("Scraping is disabled")