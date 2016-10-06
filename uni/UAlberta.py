"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import threading
import requests
import pymongo
from bs4 import BeautifulSoup
import time
import logging
import re
from ldap3 import Server, Connection, SUBTREE, ALL, LEVEL
from queue import Queue

log = logging.getLogger("UAlberta")

class UAlberta(threading.Thread):
    def __init__(self, settings):
        threading.Thread.__init__(self)
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm

        log.info("Ensuring MongoDB indexes exist")

        # want to add indexes (if they already exist, nothing will happen)
        self.db.UAlbertaCourseDesc.create_index([
            ("coursenum", pymongo.ASCENDING),
            ("subject", pymongo.ASCENDING)],
            unique=True)

        self.db.UAlbertaCourseList.create_index([
            ("id", pymongo.ASCENDING),
            ("term", pymongo.ASCENDING)],
            unique=True)

        self.db.UAlbertaSubjects.create_index([
            ("subject", pymongo.ASCENDING)],
            unique=True)

        self.db.UAlbertaProfessor.create_index([
            ("uid", pymongo.ASCENDING)],
            unique=True)

        self.db.UAlbertaTerms.create_index([
            ("term", pymongo.ASCENDING)],
            unique=True)

    def getTerms(self):
        """
        API Handler

        Returns the distinct terms in the database, along with their name and id

        :return: **dict** Keys are the ids, values are the proper names
        """
        termlist = self.db.UAlbertaCourseList.distinct("term")
        responsedict = {}
        for term in termlist:
            responsedict[str(term)] = self.db.UAlbertaTerms.find_one({"term": str(term)})['termTitle']
        return responsedict

    def getLocations(self):
        """
        API Handler

        Returns a list of all locations at UAlberta

        :return: **list** Contains 1D with the possible locations
        """
        locations = self.db.UAlbertaCourseList.distinct("location")
        response = []

        for location in locations:
            if location != "":
                response.append(location)

        return response

    def retrieveCourseDesc(self, courses):
        """
        Given a course list from an API handler, retrieves course descriptions and sorts by faculty

        Pure Function

        :param courses: **dict** List of courses from API handler
        :return: **dict** Faculty sorted dict with course descriptions
        """
        facultydict = {}

        # Get the descriptions for each subject
        for subject in courses:
            result = self.db.UAlbertaSubjects.find_one({"subject": subject})

            if result:
                del result["_id"]
                del result["subject"]
                del result["lastModified"]

                if "faculty" not in result:
                    result["faculty"] = "Other"

                if result["faculty"] not in facultydict:
                    facultydict[result["faculty"]] = {}

                facultydict[result["faculty"]][subject] = courses[subject]

                facultydict[result["faculty"]][subject]["description"] = result

        return facultydict

    def getSubjectListAll(self, term):
        """
        API Handler

        Returns all data for a given term (classes, descriptions and RMP)

        :param term: **string/int** ID of the term
        :return: **dict** All data for the term
        """
        responsedict = {}

        classes = self.db.UAlbertaCourseList.find({'term': int(term)})

        distinctProfessors = []

        # Parse each class and get their descriptions
        for course in classes:

            del course["_id"]
            if course["subject"] not in responsedict:
                responsedict[course["subject"]] = {}

            if course["coursenum"] not in responsedict[course["subject"]]:
                responsedict[course["subject"]][course["coursenum"]] = {"classes": []}

            subj = course["subject"]
            coursen = course["coursenum"]

            # Get the class description
            if "description" not in responsedict[subj][coursen]:
                result = self.db.UAlbertaCourseDesc.find_one({"coursenum": coursen, "subject": subj})
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
            del course["subject"]
            del course["coursenum"]
            del course["lastModified"]

            # Add this class to the course list
            responsedict[subj][coursen]["classes"].append(course)
            for professor in course['teachers']:
                if professor not in distinctProfessors:
                    distinctProfessors.append(professor)

        # Add the faculty sorting and course descriptions
        responsedict = self.retrieveCourseDesc(responsedict)

        # Match RMP data
        rmpobj = self.matchRMPNames(distinctProfessors)
        # Send over a list of all the professors with a RMP rating in the list
        return {"classes": responsedict, "rmp": rmpobj}

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
        # Get the RMP data for all teachers at UAlberta
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

                        if lastword.startswith(last) and firstword.startswith(first):
                            returnobj[teacher] = rmpinverted[teacher2]
                            break

        return returnobj

    def parseCourseDescription(self, req):
        """
        Removes unnessary non-letters from the req

        :param req: **string** requisite form the description of a course
        :return: **string**
        """
        char = 1
        while not req[char].isalpha():
                        char += 1
        return req[char:]

    def scrapeCourseDesc(self, conn, termid):
        """
        Retrieves all course descriptions then parses the course requisites and notes then upserts for every entry in
        the query results

        :param conn: **ldap connection object**
        :param termid: **string/int** Term ID to get courses for
        :return: **string**
        """

        log.info('obtaining course descriptions')

        # Page queries course descriptions with the search base
        searchBase = 'term=' + termid + ', ou=calendar, dc=ualberta, dc=ca'
        entry_list = conn.extend.standard.paged_search(search_base=searchBase, search_filter='(course=*)',
                                                       search_scope=LEVEL,
                                                       attributes=['catalog', 'courseDescription', 'courseTitle',
                                                                   'subject', 'units'], paged_size=400, generator=False)

        # for entry in list, parse and upsert course descriptions
        for entry in entry_list:

            # initialize course description dict
            courseDesc = {
                'coursenum': entry['attributes']['catalog'],
                'subject': entry['attributes']['subject'],
                'name': entry['attributes']['courseTitle'],
                'units': entry['attributes']['units']
            }

            # Does the course have a description?
            if 'courseDescription' in entry['attributes']:
                desc = entry['attributes']['courseDescription']

                # Removes "See note (x) above" from description?
                if "See Note" in desc:
                    desc = desc.split("See Note", 1)[0]

                # Does the course have a prerequisite?
                if 'Prerequisite' in desc:

                    # Splits the prerequisite from the description
                    info = desc.split("Prerequisite", 1)
                    prereq = self.parseCourseDescription(info[1])
                    desc = info[0]

                    # Does prerequisite have a corequisite inside of it
                    if "Corequisite" in prereq or "corequisite" in prereq:

                        #Splits the corequisite from the prereq
                        if "Corequisite" in prereq:
                            info = prereq.split("Corequisite", 1)
                        elif "corequisite" in prereq:
                            info = prereq.split("corequisite", 1)

                        prereq = info[0]

                        # Removes any "and " leftover from the splitting
                        if prereq[-4:] == "and ":
                            prereq = prereq[:-4]

                        # if the coreq is different from the prereq
                        if len(info[1]) != 1:
                            corereq = self.parseCourseDescription(info[1])
                            if prereq == "or ":
                                prereq = corereq
                            else:
                                if corereq != prereq:
                                    courseDesc['coreq'] = corereq

                    # Splits the note form the prereq
                    if "Note:" in prereq:
                        note = prereq.split("Note:", 1)
                        courseDesc['notes'] = note[1]
                        prereq = note[0]

                    courseDesc['prereq'] = prereq

                # splits the antireq from the desc
                if "Antirequisite" in desc:
                    antireq = desc.split("Antirequisite", 1)[1]
                    antireq = self.parseCourseDescription(antireq)
                    courseDesc['antireq'] = antireq
                    desc = antireq[0]

                # removes leftover info from the desc split
                if desc[-4:] == "and ":
                            desc = desc[:-4]
                courseDesc['desc'] = desc

            # Upserts course description
            self.db.UAlbertaCourseDesc.update(
                {'coursenum': entry['attributes']['catalog'], 'subject': entry['attributes']['subject']},
                {
                    '$set': courseDesc,
                    '$currentDate': {'lastModified': True}
                },
                upsert=True
            )

    def UidToName(self, uid):
        """
        Returns the name of the prof with the specified UID

        :param uid: **string** UID of the given prof
        :return: **string** Name of the prof if successful, UID if not
        """
        professor = self.db.UAlbertaProfessor.find({"uid": uid})
        if professor.count() == 0:
            # There must have been an issue when obtaining the data, just use the UID temporarily
            return uid
        else:
            # We got the name, return it
            professor = professor[0]['Name']
        return professor

    def scrapeCourseList(self, conn, termid):
        """
        Queries the course list with the termid, matches the professor to the course, upserts the initial dictionary
        then matches additional data to the object

        :param conn: **ldap connection object**
        :param termid: **string/int** Term ID to get courses for
        :return:
        """
        searchBase = 'term=' + termid + ', ou=calendar, dc=ualberta, dc=ca'
        entry_list = conn.extend.standard.paged_search(search_base=searchBase,
                                                       search_filter='(&(!(textbook=*))(class=*)(!(classtime=*)))',
                                                       search_scope=SUBTREE,
                                                       attributes=['asString', 'class', 'term', 'campus',
                                                                   'section', 'component', 'enrollStatus',
                                                                   'course', 'instructorUid'],
                                                       paged_size=400,
                                                       generator=False)

        # We want to scrape professor names from their UID's
        q = Queue()

        log.info("Filling up the Queue with Prof UIDs")

        # Fill queue with unique prof names
        queuedProfs = {}

        for entry in entry_list:
            # Ensure this class has teachers
            if 'instructorUid' in entry['attributes']:

                # We don't want to request duplicates
                if entry['attributes']['instructorUid'][0] not in queuedProfs:
                    q.put(entry['attributes']['instructorUid'][0])

                    # Add to the queuedProfs to avoid dupes
                    queuedProfs[entry['attributes']['instructorUid'][0]] = True

        # Start up the threads
        for i in range(self.settings["uidConcurrency"]):
            concurrentScraper = UIDScraper(q, self.db)
            concurrentScraper.daemon = True
            concurrentScraper.start()

        # Wait until the threads are done
        q.join()

        log.info('Parsing course data')

        # for each entry in list, upsert course into db
        for entry in entry_list:
            info = str(entry['attributes']['asString']).split(" ")

            # Seperates the subject from the coursenum
            if not info[1].isdigit():
                subject = info[0] + " " + info[1]
                coursenum = info[2]
            else:
                subject = info[0]
                coursenum = info[1]

            # Does the entry have an enrollStatus
            if entry['attributes']['enrollStatus'] == "O":
                status = "Open"
            elif entry['attributes']['enrollStatus'] == "C":
                status = "Closed"
            else:
                status = entry['attributes']['enrollStatus']

            # Initializes upsert dict
            courseList = {"subject": subject, "term": entry['attributes']['term'][0], "coursenum": coursenum,
                          "id": str(entry['attributes']['class']), "location": str(entry['attributes']['campus']),
                          "type": entry['attributes']['component'], "status": status,
                          'section': entry['attributes']['section'][0] + entry['attributes']['section'][1], "group": entry['attributes']['course'],
                          "times": ["N/A"], "rooms": ["N/A"]}

            # Does the entry have a instructor assigned to it
            if 'instructorUid' in entry['attributes']:
                courseList['teachers'] = [self.UidToName(entry['attributes']['instructorUid'][0])]
            else:
                courseList['teachers'] = ["N/A"]

            # Upserts course into db
            self.db.UAlbertaCourseList.update(
                {'id': str(entry['attributes']['class'])},
                {'$set': courseList, '$currentDate': {'lastModified': True}},
                upsert=True
            )

        # Searches for additional information
        entry_list = conn.extend.standard.paged_search(search_base=searchBase,
                                                       search_filter='(&(!(textbook=*))(class=*)(classtime=*))',
                                                       search_scope=SUBTREE,
                                                       attributes=['day', 'class', 'startTime', 'endTime',
                                                                   'location'],
                                                       paged_size=400,
                                                       generator=False)
        log.info('Matching additional data to course list')

        # for entry in list, match the days, startTime, endTime, and locations to course
        for entry in entry_list:

            # Combines day, startTime, endTime into a duration
            duration = " "
            duration = duration.join((entry['attributes']['day'][0], entry['attributes']['startTime'][0].replace(" ", ""),
                                      entry['attributes']['endTime'][0].replace(" ", "")))

            # Adds '-' btw the times
            duration = re.sub(r'^((.*?\s.*?){1})\s', r'\1 - ', duration)
            courseList = {'times': [duration]}

            # Does the class have an assigned classroom
            if 'location' in entry['attributes']:
                courseList['rooms'] = [entry['attributes']['location']]

            # Upserts additional information
            self.db.UAlbertaCourseList.update(
                {'id': str(entry['attributes']['class'])},
                {'$set': courseList, '$currentDate': {'lastModified': True}},
                upsert=True
            )

    def scrapeTerms(self, conn):
        """
        Retrieves all course descriptions then parses the course requisites and notes then upserts for every entry in
        the query results

        :param conn: **ldap connection object**
        :return: **dict** has two keys term and termTitle, values are matched to their respective keys
        """

        # Page queries all terms
        conn.search(search_base='ou=calendar, dc=ualberta, dc=ca', search_filter='(term=*)', search_scope=LEVEL,
                    attributes=['term', 'termTitle'])
        terms = []
        for entry in conn.entries:
            termDict = {}

            # If term is past summer 2016
            if int(str(entry['term'])) >= 1566:

                # Adds term to term DB
                termDict['term'] = str(entry['term'])
                termDict['termTitle'] = str(entry['termTitle']).replace("Term ", "")
                self.db.UAlbertaTerms.update(
                    {'term': str(entry['term'])},
                    {'$set': termDict},
                    upsert=True
                )
                terms.append(termDict)

        # Returns current terms
        return terms

    def updateFaculties(self, conn):
        """
        Updates the faculties with the current terms as the search base

        :param conn: **ldap connection object**
        :return:
        """
        log.info("Getting faculty list")

        # Gets all recent terms and cycles through them
        for term in self.scrapeTerms(conn):

            # If the term is a continue education term or main term update faculties
            if int(term['term']) % 3 == 0 or int(term['term']) % 10 == 0:

                # Sets the search base for the query
                searchBase = 'term='+term['term']+', ou=calendar, dc=ualberta, dc=ca'
                log.info("Updating faculties with search base " + searchBase)

                # Page queries all faculties in current term
                entry_list = conn.extend.standard.paged_search(search_base=searchBase,
                                                               search_filter='(term=*)',
                                                               search_scope=LEVEL,
                                                               attributes=['subject', 'subjectTitle', 'faculty'],
                                                               paged_size=400,
                                                               generator=False)

                # For each entry in list updates the faculty
                for entry in entry_list:
                    if 'subject' in entry['attributes']:
                        self.db.UAlbertaSubjects.update(
                            {'subject': entry['attributes']['subject']},
                            {'$set': {'subject': entry['attributes']['subject'], 'faculty': entry['attributes']['faculty'],
                                      'name': entry['attributes']['subjectTitle']},
                             '$currentDate': {'lastModified': True}
                            },
                            upsert=True
                        )
        log.info('Finished updating faculties')

    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """

        if self.settings["scrape"]:
            while True:
                try:
                    # Establish connection to LDAP server
                    server = Server('directory.srv.ualberta.ca', get_info=ALL)
                    conn = Connection(server, auto_bind=True)

                    # Updates faculties
                    self.updateFaculties(conn)

                    # Get list of current terms
                    terms = self.db.UAlbertaTerms.distinct("term")

                    # For each term, get the courses
                    for term in terms:

                        # If the term is past or equal to the summer of 2016 update courses
                        if int(term) >= 1566:
                            log.info('Obtaining ' + self.db.UAlbertaTerms.find({"term": term})[0]['termTitle'] + ' course data with id ' + term)
                            self.scrapeCourseList(conn, term)
                            self.scrapeCourseDesc(conn, term)
                    log.info('Finished scraping for UAlberta data')
                    pass
                except Exception as e:
                    log.critical("There was an critical exception | " + str(e))

                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            log.info("Scraping is disabled")


class UIDScraper(threading.Thread):
    """
    Thread that gets UID's from the passed in queue and inserts the prof's data from UAlberta
    """

    def __init__(self, q, db):
        threading.Thread.__init__(self)
        self.q = q
        self.db = db

    def run(self):
        """
        Scraping thread that gets a UID and inserts the returned prof data into the DB

        :return:
        """
        while not self.q.empty():
            # Get this UID from the queue
            thisuid = self.q.get()

            if thisuid:
                # Check if its already in the DB
                uidExists = self.db.UAlbertaProfessor.find({"uid": thisuid})

                if uidExists.count() == 0:
                    try:
                        # Get the prof data from the UAlberta directory
                        r = requests.get("http://webapps.srv.ualberta.ca/search/?type=simple&uid=true&c=" + thisuid,
                                        timeout=20)

                        # Check if the HTTP status code is ok
                        if r.status_code == requests.codes.ok:
                            # Parse the HTML
                            soup = BeautifulSoup(r.text, "lxml")
                            for tag in soup.find_all("b"):
                                info = tag.text
                                if info != "Dr " and info != "Prof ":
                                    professor = info
                                    break

                            log.info('Adding UID ' + thisuid + ' to UAlbertaProfessor db, Name: ' + professor)

                            # Upsert the data
                            self.db.UAlbertaProfessor.update({"uid": thisuid},
                                                             {'$set': {"uid": thisuid, "Name": professor}},
                                                             upsert=True)
                        else:
                            log.error("Improper HTTP Status for UID " + thisuid)
                    except:
                        log.error("Failed to obtain name for " + thisuid)

                # We're done with this class
                self.q.task_done()
            else:
                # No more items in the queue, stop the loop
                break
