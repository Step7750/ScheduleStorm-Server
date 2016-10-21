"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import threading
import pymongo
from bs4 import BeautifulSoup
import time
import logging
import requests
from datetime import datetime
import re
import json


log = logging.getLogger("MTRoyal")
verifyRequests = False


class MTRoyal(threading.Thread):

    instructionTypes = {
        "LEC": "LECTURE",
        "LAB": "LAB",
        "TUT": "TUTORIAL",
        "DD": "DISTANCE DELIVERY",
        "BL": "BLENDED DELIVERY",
        "WKT": "WORK TERM",
        "FLD": "FIELD WORK",
        "PRC": "PRACTICUM",
        "CLI": "CLINICAL",
        "IDS": "INTERNSHIP"
    }

    def __init__(self, settings):
        threading.Thread.__init__(self)
        self.settings = settings
        self.loginSession = requests.session()
        self.db = pymongo.MongoClient().ScheduleStorm
        self.invertedTypes = {v: k for k, v in self.instructionTypes.items()}

    def getTerms(self):
        """
        API Handler

        Returns the distinct terms in the database, along with their name and id

        :return: **dict** Keys are the ids, values are the proper names
        """
        termlist = self.db.MTRoyalCourseList.distinct("term")
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
        locations = self.db.MTRoyalCourseList.distinct("location")
        response = []

        for location in locations:
            if location != "":
                response.append(location)

        return response

    def getSubjectListAll(self, term):
        """
        API Handler

        Returns all data for a given term (classes, descriptions and RMP)

        :param term: **string/int** ID of the term
        :return: **dict** All data for the term
        """

        # Send over a list of all the professors with a RMP rating in the list
        return {"classes": {}, "rmp": {}}

    def login(self):
        """
        Logs into Mount Royal

        :return: **boolean** True if it logged in successfully, False if not
        """

        logindata = {
            "sid": self.settings["userid"],
            "PIN": self.settings["pin"]
        }

        loginpage = self.loginSession.get("https://mruweb.mymru.ca/prod/bwskfreg.P_AltPin", verify=False)

        if loginpage.status_code == requests.codes.ok:
            response = self.loginSession.post("https://mruweb.mymru.ca/prod/twbkwbis.P_ValLogin", data=logindata,
                                          verify=verifyRequests)
            if response.status_code == requests.codes.ok:
                return True
            else:
                return False

        else:
            return False

    def getTerms(self):
        """
        Retrieves and parses the terms list

        :return: **list**
        """
        termpage = self.loginSession.get("https://mruweb.mymru.ca/prod/bwskfcls.p_sel_crse_search")

        if termpage.status_code == requests.codes.ok:
            # parse the contents
            soup = BeautifulSoup(termpage.text, "lxml")

            response_dict = {}

            for termoption in  soup.find("select", {"name": "p_term"}).findAll("option"):
                log.debug("Processing " + termoption['value'])

                if len(termoption['value']) > 1:
                    termtext = termoption.text

                    # We want this year or next year in the text (don't want old terms)
                    thisyear = datetime.now().year

                    if str(thisyear) in termtext or str(thisyear+1) in termtext:
                        log.debug(termtext + " is within this year or the next")

                        # We dont want to present the terms that have "View Only" since users cant register in them
                        # anyways
                        if "view only" not in termtext.lower():
                            # add it to the dict
                            response_dict[termoption['value']] = termtext.strip()

            return response_dict

        else:
            return False

    def getSubjectsForTerm(self, termid):
        """
        Returns the subjects for the given term

        :param termid: **int/string** Term ID to get subjects for
        :return: **dict** Subjects in the specified term
        """

        advancedsearch = self.loginSession.post("https://mruweb.mymru.ca/prod/bwskfcls.P_GetCrse",
                                             data="rsts=dummy"
                                                  "&crn=dummy"
                                                  "&term_in=" + str(termid) +
                                                  "&sel_subj=dummy"
                                                  "&sel_day=dummy"
                                                  "&sel_schd=dummy"
                                                  "&sel_insm=dummy"
                                                  "&sel_camp=dummy"
                                                  "&sel_levl=dummy"
                                                  "&sel_sess=dummy"
                                                  "&sel_instr=dummy"
                                                  "&sel_ptrm=dummy"
                                                  "&sel_attr=dummy"
                                                  "&sel_crse="
                                                  "&sel_title="
                                                  "&sel_from_cred="
                                                  "&sel_to_cred="
                                                  "&sel_ptrm=%25"
                                                  "&begin_hh=0"
                                                  "&begin_mi=0"
                                                  "&end_hh=0"
                                                  "&end_mi=0"
                                                  "&begin_ap=x"
                                                  "&end_ap=y"
                                                  "&path=1"
                                                  "&SUB_BTN=Advanced+Search",
                                             verify=verifyRequests)

        if advancedsearch.status_code == requests.codes.ok:
            subjects = {}

            # Parse the text
            soup = BeautifulSoup(advancedsearch.text, "lxml")

            # For every subject, add it to the dict
            for subject in soup.find("select", {"name": "sel_subj"}).findAll("option"):
                subjects[subject['value']] = subject.text.strip()

            # return the subject dict
            return subjects
        else:
            return False

    def getTermClasses(self, termid, subjects):
        """
        Returns the classes for the given subjects and termid
        :param termid: **string/int** term id to fetch for
        :param subjects: **list** Contains strings of subject ids to fetch for
        :return: **String** Class Page Text
        """

        postdata = "rsts=dummy" \
                   "&crn=dummy" \
                   "&term_in=" + str(termid) + \
                   "&sel_subj=dummy" \
                   "&sel_day=dummy" \
                   "&sel_schd=dummy" \
                   "&sel_insm=dummy" \
                   "&sel_camp=dummy" \
                   "&sel_levl=dummy" \
                   "&sel_sess=dummy" \
                   "&sel_instr=dummy" \
                   "&sel_ptrm=dummy" \
                   "&sel_attr=dummy" \
                   "&sel_crse=" \
                   "&sel_title=" \
                   "&begin_hh=0" \
                   "&begin_mi=0" \
                   "&begin_ap=a" \
                   "&end_hh=0" \
                   "&end_mi=0" \
                   "&end_ap=a" \
                   "&SUB_BTN=Section+Search" \
                   "&path=1"

        # add the subjects we want
        for subject in subjects:
            postdata += "&sel_subj=" + subject

        classreply = self.loginSession.post("https://mruweb.mymru.ca/prod/bwskfcls.P_GetCrse_Advanced", data=postdata)

        if classreply.status_code == requests.codes.ok:
            if "No classes were found that meet your search criteria" not in classreply.text:
                return classreply.text
            else:
                return False
        else:
            return False

    def parseClassList(self, classlist, termid):
        """
        Parses the given class list HTML and inserts the courses into the DB
        :param classlist: **string** HTML text of a class lookup page
        :param termid: **int/string** Term ID that these classes belong to
        :return:
        """
        log.info("\n\nNEW TERM  ", termid, "\n\n ")
        classlist = BeautifulSoup(classlist, "lxml")

        # Get the table that has the classes
        displaytable = classlist.find("table", {"class": "datadisplaytable"})

        columnKeys = [False,
                      {"name": "id", "type": "int"},
                      {"name": "subject", "type": "string"},
                      {"name": "coursenum", "type": "string"},
                      {"name": "section", "type": "string"},
                      False,
                      False,
                      {"name": "type", "type": "string"},
                      {"name": "times", "type": "list"},
                      {"name": "times", "type": "list"},
                      False,
                      False,
                      {"name": "status", "type": "string"},
                      False,
                      {"name": "teachers", "type": "list"},
                      False,
                      {"name": "rooms", "type": "list"},
                      False
                      ]

        # current row index
        rowindex = 0

        # obj holding the current class being parsed
        thisClass = {}
        # Copy of the last class
        lastClassCopy = {}
        courseClasses = []

        for row in displaytable.findAll("tr"):
            title = row.find("th", {"class": "ddtitle"})

            if not title:
                # This isn't a title

                # Make sure this isn't a header
                if not row.find("th", {"class": "ddheader"}):

                    # This should be a course

                    # Boolean as to whether this is refering to the last course (another time, teacher, etc..)
                    isLastClass = False

                    # Boolean as to whether this is a new course or not, handles DB logic for pushing updates
                    newCourse = False

                    # Boolean defining whether this row is a note
                    isNote = False

                    # current index of the column
                    index = 0

                    # For every column in this row, extract class info
                    for column in row.findAll("td"):
                        if index == 0 and column.text == u'\xa0':
                            # This is an extension of the previous class (probably a note row or something)
                            isLastClass = True

                            # We can replace this class with the previous one
                            thisClass = lastClassCopy

                        if (index > 0 and isLastClass is False) or (index > 5 and isLastClass is True):
                            if isLastClass and index == 6 and "Note" in column.text:
                                # This row is a "Note"
                                isNote = True

                            elif isNote and index == 7:
                                # TODO: Parse the note (get group info)
                                pass
                            else:
                                # Just process the column
                                if index < len(columnKeys) and columnKeys[index] is not False:
                                    # Get the column text
                                    thiscolumn = column.text.strip()

                                    # update the obj for this class
                                    if index == 0 and isLastClass is False:
                                        # If this is "C", the class is closed, we don't extract anymore info
                                        if thiscolumn == "C":
                                            thisClass[columnKeys[index]["name"]] = "Closed"

                                    elif index == 3 and isLastClass is False:
                                        # parse the course number (some additional logic)
                                        # If the course number is different than the previous, set the boolean flag
                                        if columnKeys[index]["name"] in lastClassCopy \
                                                and lastClassCopy["coursenum"] != thiscolumn:
                                            newCourse = True

                                        # replace the course number
                                        thisClass[columnKeys[index]["name"]] = thiscolumn

                                    elif index == 8:
                                        # Days of the week, ex. MTF

                                        # If this isn't already a list, make it
                                        if columnKeys[index]["name"] not in thisClass:
                                            thisClass[columnKeys[index]["name"]] = []

                                        # Simply add the dates
                                        thisClass[columnKeys[index]["name"]].append(thiscolumn)

                                    elif index == 9:
                                        # 01:00 pm-01:50 pm -> 3:30PM - 5:20PM
                                        thiscolumn = thiscolumn.replace("-", " - ")\
                                                                .replace(" pm", "PM")\
                                                                .replace(" am", "AM")

                                        # Might be a TBA with no date, if so, don't add spaces
                                        if thisClass[columnKeys[index]["name"]][-1] != "":
                                            thiscolumn = " " + thiscolumn

                                        thisClass[columnKeys[index]["name"]][-1] += thiscolumn

                                    elif index == 12 and isLastClass is False:
                                        # only get the parent remainder value
                                        try:
                                            thiscolumn = int(thiscolumn)
                                            # If there are remaining seats, its open
                                            if thiscolumn > 0:
                                                thisClass[columnKeys[index]["name"]] = "Open"
                                            else:
                                                # check if the parameter is already closed, if not, wait list
                                                if columnKeys[index]["name"] not in thisClass:
                                                    thisClass[columnKeys[index]["name"]] = "Wait List"
                                        except:
                                            thisClass[columnKeys[index]["name"]] = "Closed"

                                    elif index == 14:
                                        # strip the ending p
                                        thiscolumn = thiscolumn.rstrip(' (P)').strip()

                                        # If this key isn't already in last class, make it
                                        if columnKeys[index]["name"] not in thisClass:
                                            thisClass[columnKeys[index]["name"]] = []

                                        # check if the name is already there
                                        if thiscolumn not in thisClass[columnKeys[index]["name"]]:
                                            # add it
                                            thisClass[columnKeys[index]["name"]].append(thiscolumn)

                                    elif index == 16:
                                        # handle rooms

                                        # Check if this index is already a list, if not, make it
                                        if columnKeys[index]["name"] not in thisClass:
                                                thisClass[columnKeys[index]["name"]] = []

                                        # Append this room
                                        thisClass[columnKeys[index]["name"]].append(thiscolumn)

                                    elif isLastClass is False:
                                        # nothing else to do, update the dict
                                        thisClass[columnKeys[index]["name"]] = column.text

                        index += 1


                    lastClassCopy = thisClass

                    rowindex += 1

                    if not newCourse and isLastClass is False:
                        courseClasses.append(thisClass)
                    elif newCourse:
                        log.info(courseClasses)
                        del courseClasses[:]
                        courseClasses.append(thisClass)

                    thisClass = {}


        # We need to print the very last course here
        log.info(courseClasses)




    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """

        if self.settings["scrape"]:
            while True:

                try:
                    log.info("Scraping now")
                    if self.login():
                        # Get the terms
                        terms = self.getTerms()

                        log.debug(terms)

                        if terms:
                            for term in terms:
                                # Get the subjects
                                termsubjects = self.getSubjectsForTerm(term)

                                # Get the class data for the previous subjects
                                classdata = self.getTermClasses(term, termsubjects)

                                # If we got class data, parse it
                                if classdata:
                                    self.parseClassList(classdata, term)
                except Exception as e:
                    log.critical("Exception | " + str(e))

                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            log.info("Scraping is disabled")