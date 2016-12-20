"""
Copyright (c) 2016 Stepan Fedorko-Bartos, Ceegan Hale

Under MIT License - https://github.com/Step7750/ScheduleStorm/blob/master/LICENSE.md

This file is a resource for Schedule Storm - https://github.com/Step7750/ScheduleStorm
"""

import uni
from rmp import RateMyProfessors
import json
import inspect
import time
import logging
import sys
import falcon
from threading import Lock
from wsgiref import simple_server
import hashlib

# Store the threads for each uni
uniThreads = {}

# Logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

log = logging.getLogger("main")
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("wsgiref").setLevel(logging.WARNING)

def loadSettings():
    with open("settings.json") as settingFile:
        return json.load(settingFile)

settings = loadSettings()

class v1Unis():
    """
        Retrieves list of Unis
    """
    def on_get(self, req, resp):
        responsedict = {}

        for uni in list(uniThreads.keys()):
            responsedict[uni] = {"terms": uniThreads[uni].getTerms(),
                                 "locations": uniThreads[uni].getLocations(),
                                 "name": settings["Universities"][uni]["fullname"],
                                 "rmp": settings["Universities"][uni]["rmpid"],
                                 "scraping": uniThreads[uni].isScraping}
        str_response = json.dumps(responsedict).encode('utf-8')

        # set the etag and body
        resp.etag = "W/" + hashlib.sha1(str_response).hexdigest()
        resp.body = str_response

class v1GetAllUniTermSubjects():
    """
        Retrieves all subjects and classes for a given Uni
    """
    def on_get(self, req, resp, uni, term):
        # The term must be a string since the threads represent them as such
        if uni in uniThreads and term in uniThreads[uni].getTerms():
            subject_list = json.dumps(uniThreads[uni].getSubjectListAll(term), sort_keys=True).encode('utf-8')

            # set the etag and body
            resp.etag = "W/" + hashlib.sha1(subject_list).hexdigest()
            resp.body = subject_list
        else:
            raise falcon.HTTPBadRequest('Resource Not Found',
                                        'The specified university or term was not found')

if __name__ == '__main__':

    # Instantiate the unis

    # Get the modules of uni
    unimemebers = inspect.getmembers(uni)
    rmpids = []

    # lock for file synchronization
    lock = Lock()

    log.info("Instantiating University Threads")

    # Foreach university in settings
    for university in settings["Universities"]:

        # Get the settings
        unisettings = settings["Universities"][university]

        # Set the key and lock
        unisettings["uniID"] = university
        unisettings["lock"] = lock

        # Only instantiate if they have it enabled in settings
        if "enabled" in unisettings and unisettings["enabled"]:

            # Check if rmpid is set, if so, add it to the rmpids list
            if "rmpid" in unisettings:
                rmpids.append(unisettings["rmpid"])

            foundClass = False

            # Find the module of this uni
            for member in unimemebers:
                if member[0] == university:

                    # Now find the class in the module
                    uniclasses = inspect.getmembers(member[1])

                    # Iterate the classes
                    for uniclass in uniclasses:
                        if uniclass[0] == university:
                            # Found the class, it must be the same name as the key for this Uni (ex. UCalgary)
                            uniThreads[university] = uniclass[1](unisettings)

                            log.info("Instantiated " + university + "'s thread")
                            foundClass = True

            if not foundClass:
                log.error("We couldn't find the class to instantiate for", university)

    log.info("Starting University Threads")
    # Start each Uni thread
    for uniThread in uniThreads:
        if "scrape" not in settings["Universities"][uniThread]:
            log.error(uniThread + " must have a scrape attribute!")
        else:
            if settings["Universities"][uniThread]["scrape"] is True:
                # scraping is enabled
                log.info("Starting " + uniThread + "'s thread")
                uniThreads[uniThread].start()

    # Start up the RateMyProfessors scraper if there is at least one rmp id
    if len(rmpids) > 0 and "rmpinterval" in settings:
        log.info("Starting RMP scraper")
        rmpthread = RateMyProfessors(rmpids, settings["rmpinterval"])
        rmpthread.start()

    # Run the Falcon API server
    app = falcon.API()

    # Add the routes
    app.add_route('/v1/unis', v1Unis())
    app.add_route('/v1/unis/{uni}/{term}/all', v1GetAllUniTermSubjects())

    # It is highly recommended to put this API behind a proxy such as nginx with heavy caching
    log.info("Setting up API server on port " + str(settings["port"]))
    httpd = simple_server.make_server('0.0.0.0', settings["port"], app)
    httpd.serve_forever()
