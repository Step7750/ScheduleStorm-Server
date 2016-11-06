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
from .University import University

log = logging.getLogger("UAlberta")


class UAlberta(University):
    def __init__(self, settings):
        super().__init__(settings)
        self.settings = settings
        self.db = pymongo.MongoClient().ScheduleStorm

        self.db.UAlbertaProfessor.create_index([("Name", pymongo.ASCENDING), ("uid", pymongo.ASCENDING)], unique=True)


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
            self.updateCourseDesc(courseDesc)

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

        # Searches for additional information
        times_list = conn.extend.standard.paged_search(search_base=searchBase,
                                                       search_filter='(&(!(textbook=*))(class=*)(classtime=*))',
                                                       search_scope=SUBTREE,
                                                       attributes=['day', 'class', 'startTime', 'endTime',
                                                                   'location'],
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
                          'section': entry['attributes']['section'], "group": entry['attributes']['course'],
                          "times": ["N/A"], "rooms": ["N/A"]}

            # Does the entry have a instructor assigned to it
            if 'instructorUid' in entry['attributes']:
                courseList['teachers'] = [self.UidToName(entry['attributes']['instructorUid'][0])]
            else:
                courseList['teachers'] = ["N/A"]

            # for entry in list, match the days, startTime, endTime, and locations to course
            for entry_times in times_list:

                if entry_times['attributes']['class'] == courseList['id']:

                    # Combines day, startTime, endTime into a duration
                    duration = " "
                    duration = duration.join(
                        (entry_times['attributes']['day'][0], entry_times['attributes']['startTime'][0].replace(" ", ""),
                         entry_times['attributes']['endTime'][0].replace(" ", "")))

                    # Adds '-' btw the times
                    duration = re.sub(r'^((.*?\s.*?){1})\s', r'\1 - ', duration)
                    courseList['times'] = [duration]

                    # Does the class have an assigned classroom
                    if 'location' in entry['attributes']:
                        courseList['rooms'] = [entry['attributes']['location']]
                    times_list.remove(entry_times)
            # Upserts course into db
            self.updateClass(courseList)


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

        # Gets the four most recent terms
        for item in range(1, 5):
            entry = conn.entries[len(conn.entries)-item]
            termDict = {"id": str(entry['term']), "name": str(entry['termTitle']).replace("Term ", "")}

            # Adds term to term DB
            self.updateTerm(termDict)

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
            if int(term['id']) % 3 == 0 or int(term['id']) % 10 == 0:

                # Sets the search base for the query
                searchBase = 'term='+term['id']+', ou=calendar, dc=ualberta, dc=ca'
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
                        subjectDict = {'subject': entry['attributes']['subject'],
                                       'faculty': entry['attributes']['faculty'],
                                       'name': entry['attributes']['subjectTitle']}
                        self.updateSubject(subjectDict)
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
                    terms = self.getTerms()
                    print(terms)

                    # For each term, get the courses
                    for term in terms:
                        log.info('Obtaining ' + terms[term] + ' course data with id ' + term)
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
