"""
Module to pull fire data from the MODUS project for use in Fire Flight.

User can send coordinates to API along with a perimiter value (in miles) and receive
an alert if there are active fires within that perimter.
"""

# Flask App Imports
from flask import Flask, jsonify, request, json
from flask_restful import Api, reqparse
from flask_cors import CORS


# local imports
from .models import db, Fire, FrameHash
from .resources import CheckFires, AllFires
from .functions import haversine, fires_list
from .datascience import (
    check_new_df,
    process_live_data,
    classify_fires,
    add_fires,
    check_model
)
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import os
from bs4 import BeautifulSoup
import re
from urllib.request import urlopen
import feedparser


def create_app():
    """
    Creates and configures an instance of our Flask API
    """
    app = Flask(__name__)
    # create db first

    # configure database variables
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["ENV"] = os.environ.get(
        "ENV"
    )  # apparently this doesn't really work so commenting out for now

    app.app_context().push()
    db.init_app(app)

    # enable CORS on all app routes
    CORS(app)

    # initialize the api wrapper
    api = Api(app)

    # connects resources to api endpoint
    api.add_resource(CheckFires, "/check_fires")
    api.add_resource(AllFires, "/all_fires")


    # grab RSS fires using feedparser
    @app.route("/fpfire", methods=["GET"])
    def fires_json():
        rss_fires = fires_list()
        return jsonify(rss_fires)


    @app.route("/check_rss_fires", methods=["POST"])
    def check_rss_fires(): # (lat, lon)
        values = request.get_json()

        # json type for post
        # {
        #     position: [lat, lon],
        #     radius: int
        # }

        # Get args for Haversine
        lat1, lon1 = values['position'][0], values['position'][1]
        radius = values['radius']
        
        # Initialize nearby fires
        nearby_fires = []
        other_fires = []
        
        # get list of all fires
        fires = fires_list()

        # iterate through fires
        for fire in fires:
            dist = haversine(lon1, lat1, fire['location'][0], fire['location'][1]) # haversine(lon1, lat1, lon2, lat2)
            if dist <= radius:
                nearby_fires.append(fire)
            else:
                other_fires.append(fire)
        
        return jsonify({'nearby_fires': nearby_fires, 'other_fires': other_fires})


    # grab all RSS fires - (use if feedparser is messed up)
    @app.route("/rss_fires", methods=["GET"])
    def rss_fires():
        # Open RSS page and parse lxml
        lxml = urlopen('https://inciweb.nwcg.gov/feeds/rss/incidents/')
        soup = BeautifulSoup(lxml, 'lxml')
        # Retrieve by tag
        dirty_lats = soup.find_all('geo:lat')
        dirty_lons = soup.find_all('geo:long')

        # Clean the tags out
        lats = []

        for dirty_lat in dirty_lats:
            exp = re.compile('[0-9]+.[0-9]+')
            lats.append(float(re.findall(exp, str(dirty_lat))[0]))
            

        lons = []

        for dirty_lon in dirty_lons:
            exp = re.compile('[0-9]+.[0-9]+')
            lons.append(float(re.findall(exp, str(dirty_lon))[0]))

        # instantiate location list
        location_list = []

        # iterate
        for i in range(len(lats)):
            loc = (lats[i], lons[i])
            
            location_list.append(loc)

        # Return
        return location_list


    return app

    # def make_predictions():
    #     """
    #     Ties together all DS functions, checks for new data, loads model, makes predictions,
    #     and then updates our database.
    #     """
    #     # this will return a new df if the hash isn't in our hash db, otherwise we will get a 1 indicating we don't need new predictions
    #     df = check_new_df()

    #     if type(df) == int:
    #         print("No new data")
    #         pass
    #     else:
    #         print("there's new data")
    #         # process the new data for ingestion into model
    #         df = process_live_data(df)
    #         # gets results from our model
    #         results = classify_fires(df)
    #         # add our results to the database
    #         add_fires(results)

    # # start background scheduler in paused mode, waiting to be woken up
    # scheduler = BackgroundScheduler()
    # print("add_job scheduler", datetime.datetime.now())
    # scheduler.add_job(
    #     func=make_predictions, trigger="interval", max_instances=1, minutes=60
    # )
    # scheduler.start(paused=True)

    # @app.route("/instantiate_db", methods=["POST"])
    # def instantiate_db():
    #     values = request.get_json()
    #     # expecting a json {'reset' : True, 'password' : 'ballderdash'}

    #     time_now = datetime.datetime.now()
    #     for key, item in values.items():
    #         print(key, type(item), item)

    #     if values["reset"] == 1 and values["password"] == 55689:
    #         print('dropping db')
    #         db.drop_all()
    #         print('db dropped')
    #         db.create_all()
    #         print('db created')

    #         return jsonify(
    #             {"error": False, "message": "db created successfully", "time": time_now}
    #         )
    #     else:
    #         return jsonify(
    #             {
    #                 "error": True,
    #                 "message": "either auth failed or reset was not enabled",
    #                 "time": time_now,
    #             }
    #         )

    # # run our app
    # @app.route("/update", methods=["GET"])
    # def update():
    #     # run our make_predictions function
    #     make_predictions()
    #     time_now = datetime.datetime.now()
    #     return jsonify({"predictions run at": time_now})

    # # see what model is running
    # @app.route("/check", methods=["GET"])
    # def check():
    #     # run our make_predictions function
    #     model = check_model()
    #     time_now = datetime.datetime.now()
    #     return jsonify({"model path": model, "time": time_now})

    # # start the app scheduler
    # @app.route("/start_scheduler", methods=["GET"])
    # def start_scheduler():
    #     scheduler.resume()
    #     scheduler_started = datetime.datetime.now()
    #     print("scheduler started at: ", scheduler_started)
    #     jobs = scheduler.print_jobs()
    #     return jsonify(
    #         {"scheduler started at ": scheduler_started, "scheduler jobs": jobs}
    #     )

    # # stop the app scheduler
    # @app.route("/stop_scheduler", methods=["GET"])
    # def stop_scheduler():
    #     scheduler.pause()
    #     scheduler_stopped = datetime.datetime.now()
    #     print("stopped scheduler", scheduler_stopped)
    #     return jsonify(({"stopped scheduler": scheduler_stopped}))

    # # manually update csv
    # @app.route('/data/update', methods=['GET'])
    # def check_modus_data():
    #     new_df = check_new_df()
    #     size = new_df.shape
    #     global df
    #     df = new_df

    #     return jsonify({'new df size ': size}), 201

    # # check our df size
    # @app.route('/data/size', methods=['GET'])
    # def df_size():
    #     size = df.shape
    #     return jsonify({'df_size' : size}), 201

    # # check our df head
    # @app.route('/data/head', methods=['GET'])
    # def df_head():
    #     head = df.head().to_json()
    #     return jsonify({'df_head' : head}), 201

    # start the scheduler
    # start_scheduler()