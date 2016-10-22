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

        log.info("Ensuring indexes exist...")

        self.db.MTRoyalCourseList.create_index([
            ("id", pymongo.ASCENDING),
            ("term", pymongo.ASCENDING)],
            unique=True)

        self.db.MTRoyalCourseDesc.create_index([
            ("coursenum", pymongo.ASCENDING),
            ("subject", pymongo.ASCENDING)],
            unique=True)

        self.db.MTRoyalSubjects.create_index([
            ("subject", pymongo.ASCENDING)],
            unique=True)

        self.db.MTRoyalTerms.create_index([
            ("term", pymongo.ASCENDING)],
            unique=True)

    def getTerms(self):
        """
        API Handler

        Returns the distinct terms in the database, along with their name and id

        :return: **dict** Keys are the ids, values are the proper names
        """
        termlist = self.db.MTRoyalTerms.find({"viewonly": False})

        responsedict = {}

        for term in termlist:
            responsedict[term["term"]] = term["name"]

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

    def obtainActiveTerms(self):
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

                    dbtermdict = {"term": termoption['value'], "name": termtext.strip(), "viewonly": True}

                    if str(thisyear) in termtext or str(thisyear+1) in termtext:
                        log.debug(termtext + " is within this year or the next")

                        # We dont want to present the terms that have "View Only" since users cant register in them
                        # anyways
                        if "view only" not in termtext.lower():
                            # add it to the dict
                            response_dict[termoption['value']] = termtext.strip()
                            dbtermdict["viewonly"] = False

                    # Update the term data in the DB
                    self.db.MTRoyalTerms.update(
                        {"term": dbtermdict["term"]},
                        {
                            "$set": dbtermdict,
                            "$currentDate": {"lastModified": True}
                        },
                        upsert=True
                    )

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

    def parseNotes(self, note, curdict):
        """
        Given a note for a class and the current groupings dictionary, process the notes and group up classes

        For example: Lecture 007 take one of tutorials 401-403 or 406-407 and one of labs 501-502

        This function will make sure that LEC 001 and Labs 501 and 502 have the same group number
        For a given course, this function can be repeatedly called with different classes to ensure grouping

        :param note: **String** Note to parse
        :param curdict: **dict** Current groupings
        :return:
        """
        # Any two courses that have the same group number can be taken together

        # Calculate the starting group number
        curgroupnum = 0
        for val in curdict:
            if curdict[val] > curgroupnum:
                curgroupnum = curdict[val]

        # The starting new group number is one higher than the current
        curgroupnum += 1

        # Check if this is a valid note structure
        isValidNote = re.search("(\w[ \w]*) (\d*) take ([^.]*)", note)

        if isValidNote:
            notegroups = isValidNote.groups()

            # Make sure the type is in our dict
            if notegroups[0].upper() in self.invertedTypes:
                # Now we want to split the string by "and"
                classgroups = notegroups[2]

                # split by "and" and process separately
                classgroups = classgroups.split("and")

                # Get the value of this class in the dict
                callingClass = self.invertedTypes[notegroups[0].upper()] + " " + notegroups[1]

                # set the default value
                curdict[callingClass] = curgroupnum
                curgroupnum += 1

                for group in classgroups:
                    group = group.strip()

                    # boolean as to whether the string starts with "one of"
                    oneof = False

                    # remove "one of" at the beginning
                    if group.startswith("one of"):
                        group = group.replace("one of", "").strip()
                        oneof = True

                    # Type, such as LAB, TUT
                    foundType = False

                    # Try to find the instruction type
                    instructiontype = re.search("(\D*)", group)

                    # Convert it to the code
                    if instructiontype:
                        group = group.replace(instructiontype.groups()[0], "").strip()
                        instructiontype = instructiontype.groups()[0].upper().strip()

                        # if one of, remove the last s (ex. tutorials = tutorial)
                        if oneof:
                            instructiontype = instructiontype[:len(instructiontype)-1]

                        # Get the type
                        if instructiontype in self.invertedTypes:
                            instructiontype = self.invertedTypes[instructiontype]
                            foundType = instructiontype

                    if foundType:
                        # process the statement
                        self.processNoteFragment(group, curdict, curgroupnum, callingClass, foundType)

    def classRange(self, classes):
        """
        Returns an array of classes given the range (ex. 505-507 becomes ["505", "506", "507"])

        :param classes:
        :return:
        """
        classes = classes.split("-")
        response = []

        for i in range(int(classes[0]), int(classes[1])+1):
            response.append(str(i))

        return response

    def processNoteFragment(self, group, curdict, curgroupnum, callingClass, type):
        """
        For a given note fragment, processes the meaning behind the note and adds the definition to curdict

        :param group: **String** Text fragment to process
        :param curdict: **dict** Definitions of current course groupinga
        :param curgroupnum: **int** Starting new group number
        :param callingClass: **String** Dictionary key of the originating class to group with
        :param type: **String** Type of class
        :return:
        """
        orgroups = group.split(" or ")

        for group in orgroups:
            classes = []

            # We want a list of classes that this is linked to
            # check to see if its a range
            if "-" in group:
                classes = self.classRange(group)
            elif "," in group:
                classes = group.split(",")
            else:
                classes.append(group)

            # For every class, link it
            for classv in classes:
                classcode = type + " " + classv.strip()
                if classcode in curdict:
                    # Set the calling class to this group number
                    # (maybe make an array of groups later, this may have issues)
                    curdict[callingClass] = curdict[classcode]
                else:
                    curdict[classcode] = (curgroupnum-1)

    def parseClassList(self, classlist, termid):
        """
        Parses the given class list HTML and inserts the courses into the DB
        :param classlist: **string** HTML text of a class lookup page
        :param termid: **int/string** Term ID that these classes belong to
        :return:
        """
        log.info("\n\nNEW TERM  " + str(termid) + "\n\n")
        classlist = BeautifulSoup(classlist, "lxml")

        # Get the table that has the classes
        displaytable = classlist.find("table", {"class": "datadisplaytable"})

        columnKeys = [False,
                      {"name": "id", "type": "int"},
                      {"name": "subject", "type": "string"},
                      {"name": "coursenum", "type": "string"},
                      {"name": "section", "type": "string"},
                      False,
                      {"name": "title", "type": "string"},
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
        courseGroupings = {}

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
                    columnIndex = 0

                    # For every column in this row, extract class info
                    for column in row.findAll("td"):
                        if columnIndex == 0 and column.text == u'\xa0':
                            # This is an extension of the previous class (probably a note row or something)
                            isLastClass = True

                            # We can replace this class with the previous one
                            thisClass = lastClassCopy

                        if (columnIndex > 0 and isLastClass is False) or (columnIndex > 5 and isLastClass is True):
                            if isLastClass and columnIndex == 6 and "Note" in column.text:
                                # This row is a "Note"
                                isNote = True

                            elif isNote and columnIndex == 7:
                                # Parse the note into groupings if applicable
                                self.parseNotes(column.text.strip('\n').strip(), courseGroupings)
                            else:
                                # Just process the column
                                if columnIndex < len(columnKeys) and columnKeys[columnIndex] is not False:
                                    # Get the column text
                                    thiscolumn = column.text.strip()

                                    # update the obj for this class
                                    if columnIndex == 0 and isLastClass is False:
                                        # If this is "C", the class is closed, we don't extract anymore info
                                        if thiscolumn == "C":
                                            thisClass[columnKeys[columnIndex]["name"]] = "Closed"

                                    elif columnIndex == 3 and isLastClass is False:
                                        # parse the course number (some additional logic)
                                        # If the course number is different than the previous, set the boolean flag
                                        if columnKeys[columnIndex]["name"] in lastClassCopy \
                                                and lastClassCopy["coursenum"] != thiscolumn:
                                            newCourse = True

                                        # replace the course number
                                        thisClass[columnKeys[columnIndex]["name"]] = thiscolumn

                                    elif columnIndex == 8:
                                        # Days of the week, ex. MTF

                                        # If this isn't already a list, make it
                                        if columnKeys[columnIndex]["name"] not in thisClass:
                                            thisClass[columnKeys[columnIndex]["name"]] = []

                                        # Simply add the dates
                                        thisClass[columnKeys[columnIndex]["name"]].append(thiscolumn)

                                    elif columnIndex == 9:
                                        # 01:00 pm-01:50 pm -> 3:30PM - 5:20PM
                                        thiscolumn = thiscolumn.replace("-", " - ")\
                                                                .replace(" pm", "PM")\
                                                                .replace(" am", "AM")

                                        # Might be a TBA with no date, if so, don't add spaces
                                        if thisClass[columnKeys[columnIndex]["name"]][-1] != "":
                                            thiscolumn = " " + thiscolumn

                                        thisClass[columnKeys[columnIndex]["name"]][-1] += thiscolumn

                                    elif columnIndex == 12 and isLastClass is False:
                                        # only get the parent remainder value
                                        try:
                                            thiscolumn = int(thiscolumn)
                                            # If there are remaining seats, its open
                                            if thiscolumn > 0:
                                                thisClass[columnKeys[columnIndex]["name"]] = "Open"
                                            else:
                                                # check if the parameter is already closed, if not, wait list
                                                if columnKeys[columnIndex]["name"] not in thisClass:
                                                    thisClass[columnKeys[columnIndex]["name"]] = "Wait List"
                                        except:
                                            thisClass[columnKeys[columnIndex]["name"]] = "Closed"

                                    elif columnIndex == 14:
                                        # strip the ending p
                                        thiscolumn = thiscolumn.rstrip(' (P)').strip()

                                        # If this key isn't already in last class, make it
                                        if columnKeys[columnIndex]["name"] not in thisClass:
                                            thisClass[columnKeys[columnIndex]["name"]] = []

                                        # check if the name is already there
                                        if thiscolumn not in thisClass[columnKeys[columnIndex]["name"]]:
                                            # add it
                                            thisClass[columnKeys[columnIndex]["name"]]\
                                                .append(thiscolumn.replace("  ", " "))

                                    elif columnIndex == 16:
                                        # handle rooms

                                        # Check if this index is already a list, if not, make it
                                        if columnKeys[columnIndex]["name"] not in thisClass:
                                                thisClass[columnKeys[columnIndex]["name"]] = []

                                        # Append this room
                                        thisClass[columnKeys[columnIndex]["name"]].append(thiscolumn)

                                    elif isLastClass is False:
                                        # nothing else to do, update the dict
                                        if columnKeys[columnIndex]["type"] == "int":
                                            thiscolumn = int(thiscolumn)

                                        thisClass[columnKeys[columnIndex]["name"]] = thiscolumn

                        columnIndex += 1

                    # overwrite the copy
                    lastClassCopy = thisClass

                    rowindex += 1

                    if not newCourse and isLastClass is False:
                        # just append the class
                        courseClasses.append(thisClass)
                    elif newCourse:
                        # push the classes to the db
                        #log.info(courseGroupings)
                        #log.info(courseClasses)
                        self.addClasses(courseClasses, courseGroupings, termid)
                        del courseClasses[:]
                        courseGroupings = {}
                        courseClasses.append(thisClass)

                    # reset the class dict
                    thisClass = {}

        # We need to add the very last course here
        #log.info(courseGroupings)
        #log.info(courseClasses)
        self.addClasses(courseClasses, courseGroupings, termid)

    def addClasses(self, classlist, groupings, term):
        """
        Adds the given classes in classlist to the DB with the appropriate groupings
        :param classlist: **list** Contains dictionaries of class properties
        :param groupings: **dict** Class groupings
        :param term: **int/str** Term ID
        :return:
        """
        term = int(term)

        # bool defining whether we're already fetching course descriptions for this course
        retrievingDesc = False

        for thisclass in classlist:
            thistitle = thisclass["title"]

            del thisclass["title"]

            thisclass["term"] = term
            groupkey = thisclass["type"] + " " + thisclass["section"]

            if groupkey in groupings:
                # set the group id
                thisclass["group"] = str(groupings[groupkey])
            else:
                # just set a default group of 1
                thisclass["group"] = "1"

            thisclass["location"] = "Main Campus"

            # Upsert the object
            self.db.MTRoyalCourseList.update(
                {"id": thisclass["id"], "term": thisclass["term"]},
                {
                    "$set": thisclass,
                    "$currentDate": {"lastModified": True}
                },
                upsert=True
            )

            if not retrievingDesc:
                # check whether we need to grab a description for this course
                hasDesc = self.db.MTRoyalCourseDesc.find_one({"coursenum": thisclass["coursenum"],
                                                              "subject": thisclass["subject"],
                                                              "desc": {"$exists": True}})

                if not hasDesc:
                    # We'll make a thread to try to retrieve the description for this course
                    retrievingDesc = True

                    descthread = CourseDescriptions(thisclass["coursenum"], thisclass["subject"], thistitle)
                    descthread.setDaemon(True)
                    descthread.start()

    def updateSubjects(self, subjects):
        """
        Upserts a given dictionary of subjects into the DB
        :param subjects: **dict** Keys are the subject codes, values are the names
        :return:
        """
        log.debug("Updating subject definitions")
        for subject in subjects:
            subjectname = subjects[subject]

            subjectdict = {
                "subject": subject,
                "name": subjectname
            }

            # Update the subject data in the DB
            self.db.MTRoyalSubjects.update(
                {"subject": subjectdict["subject"]},
                {
                    "$set": subjectdict,
                    "$currentDate": {"lastModified": True}
                },
                upsert=True
            )

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
                        terms = self.obtainActiveTerms()

                        log.debug(terms)

                        if terms:
                            for term in terms:
                                # Get the subjects
                                termsubjects = self.getSubjectsForTerm(term)

                                if termsubjects is not False:
                                    # Update the DB listings for the subjects
                                    self.updateSubjects(termsubjects)

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


class CourseDescriptions(threading.Thread):
    """
    Mines course descriptions from the Mount Royal Site for the specified course
    """

    mainpage = "http://www.ucalgary.ca/pubs/calendar/current/"
    fullname = ""  # full name of the subject (CPSC = Computer Science)

    def __init__(self, coursenum, subject, title):
        """
        Constructor for retrieving course descriptions

        :param coursenum: **string** Course number to retrieve the description for
        :param subject: **string** Subject to retrieve the description for
        :param title: **string** The title of the course in the course list
        :return:
        """
        threading.Thread.__init__(self)
        self.db = pymongo.MongoClient().ScheduleStorm
        self.coursenum = coursenum
        self.subject = subject
        self.title = title

    def run(self):
        urlfetch = "http://www.mtroyal.ca/ProgramsCourses/CourseListings/" \
                   + self.subject.lower() + self.coursenum + ".htm"

        # get the description page
        r = requests.get(urlfetch)

        if "page not found" not in r.text and r.status_code == requests.codes.ok:
            # setup the obj
            descobj = {"subject": self.subject, "coursenum": self.coursenum, "name": self.title}

            soup = BeautifulSoup(r.text, "lxml")

            # index for the different rows on the page
            index = 0

            # Find the title of the course and if its valid, replace the constructor title
            # Usually the course description title is more verbose/accurate than the class list version
            titlediv = soup.find("article", {"class": "welcome"}).find('h2', {'class': 'title'})
            titlediv = titlediv.text.strip().split('–')

            if len(titlediv) > 1:
                descobj["name"] = "–".join(titlediv[1:]).strip()

            # For every valid article row, parse it
            for p in soup.find("article", {"class": "welcome"}).find_all("p"):
                # Replace br with \n
                for br in p.find_all("br"):
                    br.replace_with("\n")

                # For every valid new line in p
                for row in p.text.split("\n"):
                    row = row.strip().replace('\xa0', " ")

                    if row != '':
                        # Modify the corresponding data to the row index
                        if index == 0:
                            descobj["hours"] = row
                        elif index == 1:
                            descobj["desc"] = row
                        else:
                            # Seperate the row title and data
                            row = row.split(":")
                            rowtitle = row[0].strip()
                            row = ":".join(row[1:]).strip()

                            if rowtitle.startswith("Note"):
                                descobj["note"] = row
                            elif rowtitle.startswith("Prereq"):
                                descobj["prereq"] = row
                            elif rowtitle.startswith("Coreq"):
                                descobj["coreq"] = row
                            elif rowtitle.startswith("antireq"):
                                descobj["antireq"] = row

                        index += 1


            log.debug(descobj)

            # Upsert the updated description into the DB
            self.db.MTRoyalCourseDesc.update(
                {"coursenum": descobj["coursenum"], "subject": descobj["subject"]},
                {
                    "$set": descobj,
                    "$currentDate": {"lastModified": True}
                },
                upsert=True
            )
