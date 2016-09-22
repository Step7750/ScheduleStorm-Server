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
from wsgiref import simple_server

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
                                 "rmp": settings["Universities"][uni]["rmpid"]}

        resp.body = json.dumps(responsedict)

class v1GetSubjects():
    """
        Retrieves list of all subjects for a given Uni and Term
    """
    def on_get(self, req, resp, uni, term):
        # The term must be a string since the threads represent them as such
        if uni in uniThreads and term in uniThreads[uni].getTerms():
            resp.body = json.dumps({"subjects": uniThreads[uni].getSubjectList(term)})
        else:
            raise falcon.HTTPBadRequest('Resource Not Found',
                                        'The specified university or term was not found')

class v1GetAllUniTermSubjects():
    """
        Retrieves all subjects and classes for a given Uni
    """
    def on_get(self, req, resp, uni, term):
        # The term must be a string since the threads represent them as such
        if uni in uniThreads and term in uniThreads[uni].getTerms():
            resp.body = json.dumps(uniThreads[uni].getSubjectListAll(term), sort_keys=True)
        else:
            raise falcon.HTTPBadRequest('Resource Not Found',
                                        'The specified university or term was not found')

class v1GetAllUniTermDesc():
    """
        Retrieves all course descriptions for a given Uni
    """
    def on_get(self, req, resp, uni):
        # The term must be a string since the threads represent them as such
        if uni in uniThreads:
            resp.body = json.dumps(uniThreads[uni].getCourseDescriptions())
        else:
            raise falcon.HTTPBadRequest('Resource Not Found',
                                        'The specified university was not found')

class v1GetAllUniSubDesc():
    """
        Retrieves all subject descriptions for a given Uni
    """
    def on_get(self, req, resp, uni):
        # The term must be a string since the threads represent them as such
        if uni in uniThreads:
            resp.body = json.dumps(uniThreads[uni].getSubjectDesc())
        else:
            raise falcon.HTTPBadRequest('Resource Not Found',
                                        'The specified university was not found')

if __name__ == '__main__':

    # Instantiate the unis

    # Get the modules of uni
    unimemebers = inspect.getmembers(uni)
    rmpids = []

    log.info("Instantiating University Threads")

    # Foreach university in settings
    for university in settings["Universities"]:

        # Get the settings
        unisettings = settings["Universities"][university]


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
    app.add_route('/v1/unis/{uni}/{term}', v1GetSubjects())
    app.add_route('/v1/unis/{uni}/{term}/all', v1GetAllUniTermSubjects())
    app.add_route('/v1/unis/{uni}/desc', v1GetAllUniTermDesc())
    app.add_route('/v1/unis/{uni}/subjects', v1GetAllUniSubDesc())

    # It is highly recommended to put this API behind a proxy such as nginx with heavy caching
    log.info("Setting up API server on port 3000")
    httpd = simple_server.make_server('0.0.0.0', 3000, app)
    httpd.serve_forever()
