import os
from random import randint
from flask import Flask, abort, request, jsonify
from jsonschema import validate, ValidationError
import requests
import logging
from logging import StreamHandler

import pprint
import sys


app = Flask(__name__)
app.logger.setLevel(logging.INFO)
app.logger.addHandler(StreamHandler())

update_schema = {
    'type': 'object',
    'properties': {
        'update_id': {'type': 'integer'},
        'message': {
            'type': 'object',
            'properties': {
                'message_id': {'type': 'integer'},
                'text': {'type': 'string'},
                'chat': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'}
                    },
                    "required": ["id"]
                }
            },
            "required": ["message_id"]
        },
    },
    "required": ["update_id"]
}

def make_map_url(location, pokemons):
    lat = location["latitude"]
    lon = location["longitude"]
    ll = str(lon)+","+str(lat)
    poke_poi = [str(pokemon['lon'])+
                ","+
                str(pokemon['lat'])+
                ",pm2ywl"+
                str(pokemon["id"])
                    for pokemon in pokemons]
    return "https://static-maps.yandex.ru/1.x/?ll="+ll+"&z=16&l=map&pt="+"~".join(poke_poi)

from pogom.models import Pokemon, create_tables
from pogom.search import generate_location_steps
from threading import Thread
from pogom.utils import get_args, insert_mock_data
from pogom.search import search_loop, send_map_request
from pogom.pgoapi import PGoApi
api = PGoApi()

from math import sin, cos, atan2, sqrt, radians
def calc_distance(start_lat_lon, finish_lat_lon, return_in="km"):
    # great-circle distance between two points on a sphere from their longitudes and latitudes
    return_in_to_multiplier = {"km":1,
                               "kilometer":1,
                               "kilometer":1,
                               "meter":1000,
                               "meters":1000,
                               "m":1000}
    lat1, lon1 = map(float, start_lat_lon)
    lat2, lon2 = map(float, finish_lat_lon)
    radius = 6371 # km. earth

    dlat = radians(lat2-lat1)
    dlon = radians(lon2-lon1)

    a = (sin(dlat/2) * sin(dlat/2) +
         cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2) * sin(dlon/2))
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    d = radius * c * return_in_to_multiplier[return_in]

    return d

from datetime import datetime
from datetime import timedelta
from base64 import b64encode


def get_pokemons(location):
    lat = location["latitude"]
    lon = location["longitude"]
    logged_in = api.login("google", os.environ.get('GOOGLE_LOGIN'), os.environ.get('GOOGLE_PSWD'))
    sys.stderr.write("Login result: "+str(logged_in)+"\n")
    map_dict = send_map_request(api, [lat, lon, 0])
    sys.stderr.write("============\n")
    sys.stderr.write(pprint.pformat(map_dict))
    sys.stderr.write("============\n")
    pokemons_data = {}
    pokemons = []

    cells = map_dict['responses']['GET_MAP_OBJECTS']['map_cells']
    for cell in cells:
        for p in cell.get('wild_pokemons', []):
            d_t = datetime.utcfromtimestamp(
                (p['last_modified_timestamp_ms'] +
                 p['time_till_hidden_ms']) / 1000.0)
            pokemons_data[p['encounter_id']] = {
                'encounter_id': b64encode(str(p['encounter_id'])),
                'spawnpoint_id': p['spawnpoint_id'],
                'pokemon_id': p['pokemon_data']['pokemon_id'],
                'latitude': p['latitude'],
                'longitude': p['longitude'],
                'disappear_time': d_t
            }
            pokemons.append(
                {
                    'id': p['pokemon_data']['pokemon_id'],
                    'lat': p['latitude'],
                    'lon': p['longitude']
                }
            )
            if len(pokemons) > 10:
                break
    return pokemons


@app.route('/hodor/<token>', methods=['POST'])
def hodor(token):
    if os.environ.get('TELEGRAM_TOKEN') is None:
        abort(500)
    if token != os.environ.get('TELEGRAM_TOKEN'):
        abort(400, extra='token does not match')
    try:
        validate(request.json, update_schema)
    except ValidationError as detail:
        abort(400, detail.args[0])

    message = request.json["message"].get("text", "<None>")
    location = request.json["message"].get("location")
    app.logger.info('chat id={0}, text={1}, location={2}'.format(
        request.json["message"]["chat"]["id"],
        str(message),
        str(location))
    )
    if location is None:
        res = {
            'chat_id': request.json["message"]["chat"]["id"],
            'text': "Send me location"
        }
    else:
        pokemons = get_pokemons(location)
        res = {
            'chat_id': request.json["message"]["chat"]["id"],
            'text': "your location: "+str(location) +\
                    "\n"+make_map_url(location, pokemons)
        }
    requests.post('https://api.telegram.org/bot{0}/SendMessage'.format(os.environ.get('TELEGRAM_TOKEN')), data=res)
    return jsonify(res), 200

def start_locator_thread(args):
    search_thread = Thread(target=search_loop, args=(args,))
    search_thread.daemon = True
    search_thread.name = 'search_thread'
    search_thread.start()


if __name__ == '__main__':
    args = get_args()
    create_tables()
    #if not args.mock:
    #start_locator_thread(args)
    #else:
    #insert_mock_data()

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT')))
