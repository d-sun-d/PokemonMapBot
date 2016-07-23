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


HODOR_QUOTES = ['Hodor!', 'Hodor.', 'Hodor! Hodor!', 'HOOODOORRR!!']


@app.route('/hodor/<token>', methods=['POST'])
def hodor(token):
    if os.environ.get('TELEGRAM_TOKEN') is None:
        abort(500)
    if token != os.environ.get('TELEGRAM_TOKEN'):
        abort(400, extra='token does not match')
    try:
        validate(request.json, update_schema)
    except ValidationError as detail:
        sys.stderr.write(pprint.pformat(request.json))
        abort(400, detail.args[0])
    app.logger.info('chat id={0}, text={1}'.format(request.json["message"]["chat"]["id"], request.json["message"]["text"]))
    res = {
        'chat_id': request.json["message"]["chat"]["id"],
        'text': HODOR_QUOTES[randint(0, len(HODOR_QUOTES) - 1)]
    }
    requests.post('https://api.telegram.org/bot{0}/SendMessage'.format(os.environ.get('TELEGRAM_TOKEN')), data=res)
    return jsonify(res), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT')))
