import os
from transliterate import translit
import sqlite3
from zoneinfo import ZoneInfo
from datetime import date, datetime
from flask import Flask, current_app, g, jsonify
from flask_restful import Resource, Api, reqparse


class GeoObject(Resource):
    def get(self, geonameid):
        return jsonify(dict(get_object_from_db(geonameid)))

class GeoSearch(Resource):
    def get(self, page=1, rows=20):
        parser = reqparse.RequestParser()
        parser.add_argument('page', type=int, location='args')
        parser.add_argument('rows', type=int, location='args')
        args = parser.parse_args()
        if args['page'] is not None:
            page = args['page']
        if args['rows'] is not None:
            rows = args['rows']

        return jsonify([dict(row) for row in get_rows_from_db(page, rows)])

class GeoCompare(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('first_name', location='args')
        parser.add_argument('second_name',location='args')
        args = parser.parse_args()

        first_name = translit(args['first_name'], 'ru', reversed=True)
        second_name = translit(args['second_name'], 'ru', reversed=True)
        return jsonify(get_objects_by_name(first_name, second_name))

class GeoGlossary(Resource):
    def get(self):
        parser = reqparse.RequestParser()
        parser.add_argument('name', location='args')
        args = parser.parse_args()
        name = translit(args['name'], 'ru', reversed=True)

        return jsonify(get_whole_name(name))

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row

    return g.db

def close_db(e=None):
    db = g.pop('db', None)

    if db is not None:
        db.close()

def init_db():
    db = get_db()

    with open('tt_define_db.sql') as f:
        db.executescript(f.read())
    
    with open('RU.txt') as f:
        for line in f:
            object_data = line.split('\t')
            for entity in object_data:
                if entity:
                    if entity.isdecimal():
                        entity = int(entity)
                    elif entity.replace('.', '').isdecimal():
                        entity = float(entity)
                else:
                    entity = None
            object_data[18] = object_data[18].removesuffix('\n')
            object_data[18] = date.fromisoformat(object_data[18])
            db.execute(
                'insert into geo_object values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (object_data)
            )
        db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    if not os.path.exists(current_app.config['DATABASE']):
        init_db()

def get_object_from_db(geonameid):
    db = get_db()
    error = {'error': None}
    if not geonameid:
        error['error'] = 'Please, enter the id at first.'
    else:
        info = db.execute(
            'select * from geo_object where geonameid = ?',
            (geonameid,)
        ).fetchone()
        if info is None:
            error['error'] = 'Incorrect id.'

    if error['error'] is None:
        return info
    return error

def get_rows_from_db(page, rows):
    db = get_db()
    error = {'error': None}
    min_geonameid = db.execute(
        'select min(geonameid) from geo_object'
    ).fetchone()
    if not page:
        error['error'] = 'Please, enter the number of page at first.'
    elif not rows:
        error['error'] = 'Please, enter the number of rows at first.'
    else:
        info = db.execute(
            'select * from geo_object where geonameid >= ?',
            (((page-1)*rows)+min_geonameid['min(geonameid)'],)
        ).fetchmany(rows)
        if info is None:
            error['error'] = 'Incorrect values.'

    if error['error'] is None:
        return info
    return [error]

def get_objects_by_name(first_name, second_name):
    db = get_db()
    error = {'error': None}
    if not first_name or not second_name:
        error['error'] = 'Please, enter the name of the object at first.'
    else:
        first_info = db.execute(
            'select * from geo_object where asciiname = ? order by population',
            (first_name,)
        ).fetchone()
        second_info = db.execute(
            'select * from geo_object where asciiname = ? order by population',
            (second_name,)
        ).fetchone()
    
        if first_info is None or second_info is None:
            error['error'] = 'Incorrect name.'
        else:
            compare_info = {}
            dt = datetime.today()
            first_tz = ZoneInfo(first_info['timezone']).utcoffset(dt)
            second_tz = ZoneInfo(second_info['timezone']).utcoffset(dt)
            compare_info['is equal timezone'] = (first_tz == second_tz)
            if not compare_info['is equal timezone']:
                compare_info['difference'] = str(abs(first_tz - second_tz))
            compare_info['id northernmost'] = first_info['geonameid'] if first_info['latitude'] > second_info['latitude'] else (second_info['geonameid'] if first_info['latitude'] < second_info['latitude'] else None)
    
    if error['error'] is None:
        return {'first object' : dict(first_info), 'second object' : dict(second_info), 'compare result' : compare_info}
    return error

def get_whole_name(name):
    db = get_db()
    error = {'error': None}
    if not name:
        error['error'] = 'Please, enter the name of the object at first.'
    else:
        info = db.execute(
            'select asciiname from geo_object where asciiname like ? order by population',
            (name + '%',)
        ).fetchall()

        options = []
        if info is None:
            error['error'] = 'Incorrect name.'
        else:
            for row in info:
                options.append(translit(row['asciiname'], 'ru'))

    if error['error'] is None:
        return options
    return error

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, 'tt_db.sqlite'),
    )
    app.config.from_pyfile('config.py', silent=True)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    with app.app_context():
        init_app(app)
    
    api = Api(app)
    api.add_resource(GeoObject, '/<int:geonameid>')
    api.add_resource(GeoSearch, '/')
    api.add_resource(GeoCompare, '/compare')
    api.add_resource(GeoGlossary, '/glossary')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(port=8000, host='127.0.0.1')
