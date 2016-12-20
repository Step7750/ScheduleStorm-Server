"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import threading
import pymongo
import logging
import json
from time import time, sleep
from collections import OrderedDict
from traceback import print_exc


class University(threading.Thread):
    """
    Generic University class that every university should inherit
    """
    types = {
        "LECTURE": "LEC",
        "TUTORIAL": "TUT",
        "LAB": "LAB",
        "SEMINAR": "SEM",
        "LECTURE/LAB": "LCL",
        "LAB/LECTURE": "LBL",
        "CLINIC": "CLN",
        "DISTANCE DELIVERY": "DD",
        "BLENDED DELIVERY": "BL",
        "WORK TERM": "WKT",
        "FIELD WORK": "FLD",
        "PRACTICUM": "PRC",
        "CLINICAL": "CLI",
        "INTERNSHIP": "IDS"
    }

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm
        self.log = logging.getLogger(self.settings["uniID"])
        self.isScraping = False
        self.ensureIndexes()

    def ensureIndexes(self):
        """
        Ensures the indexes exist for each university table

        :return:
        """
        self.db.Terms.create_index([
            ("id", pymongo.ASCENDING),
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

        self.db.ClassList.create_index([
            ("id", pymongo.ASCENDING),
            ("term", pymongo.ASCENDING),
            ("uni", pymongo.ASCENDING)],
            unique=True)

        self.db.ClassList.create_index([
            ("term", pymongo.ASCENDING),
            ("uni", pymongo.ASCENDING)])

    def getLocations(self):
        """
        API Handler

        Returns a list of all distinct locations at this university

        :return: **list** Distinct locations for this university
        """
        locations = self.db.ClassList.distinct("location", {"uni": self.settings["uniID"]})
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

    def typeNameToAcronym(self, name):
        """
        Returns the type acronym given the name

        If the name doesn't match, it returns False

        :param name: **String** Type name to get the acronym for
        :return: **String/bool** Acronym of the name if successful, False if not
        """
        name = name.upper()

        if name in self.types:
            return self.types[name]
        else:
            return False


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
        self.db.Terms.update({"uni": self.settings["uniID"]}, {"$set": {"enabled": False}}, upsert=False, multi=True)

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

    def getCourseDescription(self, coursenum, subject):
        """
        Returns whether the given course has a description or not

        :param coursenum: **string** Number of the course (ex. 545A or 545)
        :param subject: **string** Subject code (ex. CPSC)
        :return: **obj/boolean** Description obj if the course has a description, False is not
        """
        return self.db.CourseDesc.find_one(
            {
                "coursenum": coursenum,
                "subject": subject,
                "uni": self.settings["uniID"]
            }
        )

    def updateSubject(self, subject):
        """
        Upserts a given subject into the DB

        :param subject: **dict** Keys are the subject codes, values are the names
        :return:
        """
        if "subject" not in subject:
            self.log.critical("Subject object doesn't contain the subject key")
        else:
            subject["uni"] = self.settings["uniID"]

            # Update the subject data in the DB
            self.db.Subjects.update(
                {
                    "subject": subject["subject"],
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

        :param subjects: **list** List of subject objects to upsert
        :return:
        """
        for subject in subjects:
            self.updateSubject(subject)

    def getSubject(self, query):
        """
        Returns a subject if it matches the given query

        :param query: **dict** Object with fields that you'd like the subject to match
        :return: **dict/bool** If successful, the subject object, False if not
        """
        query["uni"] = self.settings["uniID"]

        return self.db.Subjects.find_one(query)


    def updateClass(self, classobj):
        """
        Upserts the given class into the DB

        :param classobj: **dict** Attributes of class to insert into the DB
        :return:
        """
        requiredKeys = ["id", "group", "location", "rooms", "status", "teachers", "term", "times", "type"]
        hasAllKeys = True

        # Make sure it has each key
        for key in requiredKeys:
            if key not in classobj:
                hasAllKeys = False
                break

        if not hasAllKeys:
            self.log.critical("The following class doesn't have all of the required keys, please refer to API docs: "
                              + str(classobj))
        else:
            # upsert the class to the DB
            classobj["uni"] = self.settings["uniID"]
            # force term to be a string
            classobj["term"] = str(classobj["term"])

            self.db.ClassList.update(
                {
                    "id": classobj["id"],
                    "term": classobj["term"],
                    "uni": classobj["uni"]
                },
                {
                    "$set": classobj,
                    "$currentDate": {"lastModified": True}
                },
                upsert=True
            )

    def updateClasses(self, classes):
        """
        Upserts many classes into the DB

        :param classes: **list** Of class dicts
        :return:
        """
        for classobj in classes:
            self.updateClass(classobj)

    def matchRMPNames(self, distinctteachers):
        """
        Given a list of teachers to match RMP data to, this function obtains all RMP data and tries to match the names
        with the distinctteachers list and returns the matches

        We first check whether the constructed name is simply the same in RMP
        If not, we check whether the first and last words in a name in RMP is the same
        If not, we check whether any first and last words in the teachers name has a result in RMP that starts
            with the first and last words
        If not, we give up and don't process the words

        Most teachers should have a valid match using this method, many simply don't have a profile on RMP
        Around 80%+ of valid teachers on RMP should get a match

        False positives are possible, but highly unlikely given that it requires the first and last name of the
        wrong person to start the same way

        :param distinctteachers: **list** Distinct list of all teachers to find an RMP match for
        :return: **dict** Matched teachers and their RMP ratings
        """
        # Get the RMP data for all teachers at UCalgary
        rmp = self.db.RateMyProfessors.find({"school": self.settings["rmpid"]})

        returnobj = {}

        # We want to construct the names of each teacher and invert the results for easier parsing
        # and better time complexity
        rmpinverted = {}

        for teacher in rmp:
            # Construct the name
            fullname = ""
            if "firstname" in teacher:
                fullname += teacher["firstname"]
            if "middlename" in teacher:
                fullname += " " + teacher["middlename"]
            if "lastname" in teacher:
                fullname += " " + teacher["lastname"]

            # remove unnecessary fields
            del teacher["_id"]
            del teacher["lastModified"]
            del teacher["school"]

            rmpinverted[fullname] = teacher

        # Iterate through each distinct teacher
        for teacher in distinctteachers:
            if teacher in rmpinverted:
                # We found an instant match, add it to the return dict
                returnobj[teacher] = rmpinverted[teacher]
            else:
                # Find the first and last words of the name
                teacherNameSplit = teacher.split(" ")
                lastword = teacherNameSplit[-1]
                firstword = teacherNameSplit[0]

                # Check to see if the first and last words find a match (without a middle name)
                namewithoutmiddle = firstword + " " + lastword

                if namewithoutmiddle in rmpinverted:
                    # Found the match! Add an alias field
                    returnobj[teacher] = rmpinverted[namewithoutmiddle]
                else:
                    # Find a teacher in RMP that had the first and last words of their name starting the
                    # respective words in the original teacher's name
                    for teacher2 in rmpinverted:
                        splitname = teacher2.split(" ")
                        first = splitname[0]
                        last = splitname[-1]

                        # If the first word is larger, use that name as the reference point
                        if len(firstword) < len(first):
                            if last.startswith(lastword) and first.startswith(firstword):
                                returnobj[teacher] = rmpinverted[teacher2]
                                break
                        else:
                            if lastword.startswith(last) and firstword.startswith(first):
                                returnobj[teacher] = rmpinverted[teacher2]
                                break

        return returnobj

    def retrieveSubjectDesc(self, courses):
        """
        Given a course list from an API handler, retrieves course descriptions and sorts by faculty if applicable

        Pure Function

        :param courses: **dict** List of courses from API handler
        :return: **dict** Faculty (if applicable) sorted dict with course descriptions
        """
        response = {}

        # Check if this Uni supports faculties
        supportsFaculties = False

        facultyCount = self.db.Subjects.find({"uni": self.settings["uniID"], "faculty": {"$exists": True}}).count()

        if facultyCount > 0:
            supportsFaculties = True
        else:
            # response doesn't have faculties, so it has the same structure as courses
            response = courses

        # Get the descriptions for each subject
        for subject in courses:
            result = self.db.Subjects.find_one({"subject": subject, "uni": self.settings["uniID"]})

            if result:
                del result["_id"]
                del result["subject"]
                del result["lastModified"]

                if supportsFaculties:
                    if "faculty" not in result:
                        result["faculty"] = "Other"

                    if result["faculty"] not in response:
                        response[result["faculty"]] = {}

                    response[result["faculty"]][subject] = courses[subject]

                    response[result["faculty"]][subject]["description"] = result
                else:
                    response[subject]["description"] = result

        return response

    def getSubjectListAll(self, term):
        """
        API Handler

        Returns all data for a given term (classes, descriptions and RMP)

        :param term: **string/int** ID of the term
        :return: **dict** All data for the term
        """
        responsedict = {}

        classes = self.db.ClassList.find({"term": term, "uni": self.settings["uniID"]})

        distinctteachers = []

        # Parse each class and get their descriptions
        for classv in classes:
            del classv["_id"]

            if classv["subject"] not in responsedict:
                responsedict[classv["subject"]] = {}

            if classv["coursenum"] not in responsedict[classv["subject"]]:
                responsedict[classv["subject"]][classv["coursenum"]] = {"classes": []}

            subj = classv["subject"]
            coursen = classv["coursenum"]

            # Get the class description
            if "description" not in responsedict[subj][coursen]:
                result = self.getCourseDescription(coursen, subj)

                if result:
                    # Remove unneeded fields
                    del result["_id"]
                    del result["subject"]
                    del result["coursenum"]
                    del result["lastModified"]

                    responsedict[subj][coursen]["description"] = result
                else:
                    responsedict[subj][coursen]["description"] = False

            # Remove unneeded fields
            del classv["subject"]
            del classv["coursenum"]
            del classv["lastModified"]

            # Add this class to the course list
            responsedict[subj][coursen]["classes"].append(classv)

            # Find distinct teachers and append them to distinctteachers
            for teacher in classv["teachers"]:
                if teacher not in distinctteachers and teacher != "Staff":
                    distinctteachers.append(teacher)


        # Add the faculty sorting and course descriptions
        responsedict = self.retrieveSubjectDesc(responsedict)

        # Match RMP data
        rmpobj = self.matchRMPNames(distinctteachers)

        # Send over a list of all the professors with a RMP rating in the list
        return {"classes": responsedict, "rmp": rmpobj}

    def scrape(self):
        self.log.critical("You must override the scrape method!")

    def updateLastScraped(self):
        """
        Updates the "lastScraped" property of this university in the settings file

        :return:
        """
        with self.settings["lock"]:
            with open("settings.json") as settingFile:
                settings = json.load(settingFile, object_pairs_hook=OrderedDict)
                settings["Universities"][self.settings["uniID"]]["lastUpdated"] = int(time())

                with open('settings.json', 'wt') as out:
                    json.dump(settings, out, indent=4)

    def run(self):
        if "scrapeinterval" not in self.settings or not isinstance(self.settings["scrapeinterval"], int) \
                or self.settings["scrapeinterval"] < 0:
            self.log.critical("No 'scrapeinterval' set, aborting")
        else:
            # check if we need to sleep given lastUpdated
            if "lastUpdated" in self.settings:
                # amount of seconds since the last successful update
                lastUpdate = int(time()) - self.settings["lastUpdated"]

                # if it was less than scrapeinterval, sleep for the amount of time
                if 0 < lastUpdate < self.settings["scrapeinterval"]:
                    self.log.info("Sleeping for " + str(self.settings["scrapeinterval"] - lastUpdate) + "s due to "
                                                                                                        "lastUpdated")
                    sleep(self.settings["scrapeinterval"] - lastUpdate)

            while True:
                self.log.info("Starting to scrape updated course info")
                self.isScraping = True

                try:
                    self.scrape()
                    self.updateLastScraped()
                except Exception as e:
                    print_exc()

                self.log.info("Done scraping, sleeping for " + str(self.settings["scrapeinterval"]) + "s")
                self.isScraping = False

                # Sleep for the specified interval
                sleep(self.settings["scrapeinterval"])
