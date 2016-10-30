"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import threading
import pymongo
import logging


class University(threading.Thread):
    """
    Generic University class that every university should inherit
    """

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm
        self.log = logging.getLogger(self.settings["uniID"])
        self.ensureIndexes()

    def ensureIndexes(self):
        """
        Ensures the indexes exist for each university table

        :return:
        """
        self.db.Terms.create_index([
            ("term", pymongo.ASCENDING),
            ("uni", pymongo.ASCENDING)],
            unique=True)

        self.db.CourseDesc.create_index([
            ("coursenum", pymongo.ASCENDING),
            ("subject", pymongo.ASCENDING),
            ("uni", pymongo.ASCENDING)],
            unique=True)

        self.db.Subjects.create_index([
            ("subject", pymongo.ASCENDING),
            ("uni", pymongo.ASCENDING)],
            unique=True)

    def getLocations(self):
        """
        API Handler

        Returns a list of all distinct locations at this university

        :return: **list** Distinct locations for this university
        """
        locations = self.db.CourseList.distinct("location", {"uni": self.settings["uniID"]})
        response = []

        for location in locations:
            if location != "":
                response.append(location)

        return response

    def getTerms(self):
        """
        API Handler

        Returns the enabled terms in the database with their ids and names

        :return: **dict** Keys are the ids, values are the proper names
        """
        # get enabled terms for this university
        termlist = self.db.Terms.find({"uni": self.settings["uniID"], "enabled": True})

        responsedict = {}

        # Iterate through the termlist and set the response with keys being the ids and values being the names
        for term in termlist:
            responsedict[str(term["id"])] = term["name"]

        return responsedict

    def updateTerms(self, terms):
        """
        Given a list of term objects, sets them as the only enabled terms in the DB and updates their objects

        :param terms: **list** Contains a list of all enabled term objects
        :return:
        """
        # Set every term to disabled (we don't display them to the user)
        self.resetEnabledTerms()

        for term in terms:
            self.updateTerm(term)

    def resetEnabledTerms(self):
        """
        Sets all the terms for this university to not be enabled

        :return:
        """
        self.db.Terms.update({"uni": self.settings["uniID"]}, {"$set": {"enabled": False}}, {"multi": True})

    def updateTerm(self, term):
        """
        Upserts the specified term obj

        Note: This method does not reset all the enabled terms

        :param term: **dict** Term attributes to insert
        :return:
        """
        term["enabled"] = True
        term["uni"] = self.settings["uniID"]

        self.db.Terms.update(
            {
                "id": term["id"],
                "uni": term["uni"]
            },
            {
                "$set": term,
                "$currentDate": {"lastModified": True}
            },
            upsert=True
        )

    def getTerm(self, termid):
        """
        Returns the term DB entry corresponding to the specified termid

        :param termid: **int/str** Term ID to fetch for
        :return: **obj/bool** Term Obj is succesful, False is not
        """
        return self.db.Terms.find_one({"uni": self.settings["uniID"], "id": str(termid)})

    def updateCourseDesc(self, coursedesc):
        """
        Upserts the given course description object into the DB

        :param coursedesc: **dict** Object to insert into the DB
        :return:
        """
        if "subject" not in coursedesc or "coursenum" not in coursedesc:
            self.log.critical("Course description doesn't have both subject and coursenum keys")
        else:
            coursedesc["uni"] = self.settings["uniID"]
            self.db.CourseDesc.update(
                {
                    "coursenum": coursedesc["coursenum"],
                    "subject": coursedesc["subject"],
                    "uni": coursedesc["uni"]
                },
                {
                    "$set": coursedesc,
                    "$currentDate": {"lastModified": True}
                },
                upsert=True
            )

    def updateSubject(self, subject):
        """
        Upserts a given subject into the DB

        :param subject: **dict** Keys are the subject codes, values are the names
        :return:
        """
        if "subject" not in subject or "name" not in subject:
            self.log.critical("Subject doesn't contain both the name and it's subject")
        else:
            subject["uni"] = self.settings["uniID"]

            # Update the subject data in the DB
            self.db.Subjects.update(
                {
                    "subject": subjectdict["subject"],
                    "uni": subject["uni"]
                },
                {
                    "$set": subject,
                    "$currentDate": {"lastModified": True}
                },
                upsert=True
            )

    def updateSubjects(self, subjects):
        """
        Upserts a given list of subjects into the DB

        :param subject: **list** List of subject objects to upsert
        :return:
        """
        for subject in subjects:
            self.updateSubject(subject)

    def run(self):
        self.log.critical("You must overwrite the run method for " + self.settings["uniID"])
