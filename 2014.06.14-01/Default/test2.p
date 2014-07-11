__author__ = 'Ninad'

import os, sys

filename = os.path.basename(__file__)

def load():
    information = {
        uuid: 'EEA8B330-A999-4D9F-89AB-D341330B6121',
        description: 'This is test2 module',
        sequence: [
            'start',
            'parse',
            'stop'
        ],
        version: {
            major: 1,
            minor: 0,
            patch: 5,
        }
    }

    return information