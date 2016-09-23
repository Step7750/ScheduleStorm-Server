"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import threading
import pymongo
import time
import logging
from ldap3 import Server, Connection, ALL

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
                    #log.info(server.info)
                    log.info(conn.search('ou=calendar, dc=ualberta, dc=ca', '(term=1580)'))
                    log.info(conn.entries)
                    pass
                except Exception as e:
                    log.critical("There was an critical exception | " + str(e))

                # Sleep for the specified interval
                time.sleep(self.settings["scrapeinterval"])
        else:
            log.info("Scraping is disabled")