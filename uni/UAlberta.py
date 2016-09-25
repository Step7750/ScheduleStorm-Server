"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import threading
import pymongo
import time
import logging
from ldap3 import Server, Connection, SUBTREE, ALL

log = logging.getLogger("UAlberta")


class UAlberta(threading.Thread):
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
        termlist = self.db.UAlbertaCourseList.distinct("term")
        responsedict = {}

        for term in termlist:
            responsedict[str(term)] = self.termIDToName(term)

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

    def getSubjectListAll(self, term):
        """
        API Handler

        Returns all data for a given term (classes, descriptions and RMP)

        :param term: **string/int** ID of the term
        :return: **dict** All data for the term
        """

        # Send over a list of all the professors with a RMP rating in the list
        return {"classes": {}, "rmp": {}}

    def run(self):
        """
        Scraping thread that obtains updated course info

        :return:
        """

        if self.settings["scrape"]:
            while True:
                try:
                    server = Server('directory.srv.ualberta.ca', get_info=ALL)
                    conn = Connection(server, auto_bind=True)
                    entry_list = conn.extend.standard.paged_search(search_base='ou=calendar, dc=ualberta, dc=ca',
                                                      search_filter='(&(term=1570)(!(textbook=*))(class=*)(!(classtime=*)))',
                                                      search_scope= SUBTREE,
                                                      attributes=['asString', 'class', 'term', 'campus', 'classNotes',
                                                                  'component', 'enrollStatus'],
                                                      paged_size=400,
                                                      generator=False)
                    totalEntries = len(entry_list)
                    print('Total Entries:', totalEntries)
                    result = self.db.UAlbertaCourseList.delete_many({})
                    for entry in entry_list:
                        info = str(entry['attributes']['asString']).split(" ")
                        if len(info[0]) <= 2:
                            subject = info[0] + " " + info[1]
                            coursenum = info[2]
                        else:
                            subject = info[0]
                            coursenum = info[1]
                        term = entry['attributes']['term'][0]
                        if 'classNotes' in entry['attributes']:
                            self.db.UAlbertaCourseList.insert(
                                {"subject": subject, "term": term,
                                 "coursenum": coursenum, "id": str(entry['attributes']['class']),
                                 "location": str(entry['attributes']['campus']),
                                 "notes": entry['attributes']['classNotes'],
                                 "type": entry['attributes']['component'],
                                 "status": entry['attributes']['enrollStatus']}
                            )
                        else:
                            self.db.UAlbertaCourseList.insert(
                                {"subject": subject, "term": term,
                                 "coursenum": coursenum, "id": str(entry['attributes']['class']),
                                 "location": str(entry['attributes']['campus']),
                                 "type": entry['attributes']['component'],
                                 "status": entry['attributes']['enrollStatus']}
                            )
                    pass
                except Exception as e:
                    log.critical("There was an critical exception | " + str(e))

                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            log.info("Scraping is disabled")