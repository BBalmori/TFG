import configparser

from flask import Flask, request, jsonfy
from flask_restful import Resource, Api
import pymysql

config = configparser.ConfigParser()
config.read('config.config')

assert 'user' in config['mysql'], 'Config file does not have an User value'
assert 'password' in config['mysql'], 'Config file does not have a Password value'
assert 'host' in config['mysql'], 'Config file does not have a Host value'
assert 'database' in config['mysql'], 'Config file does not have a Database value'

# CREO UNA CONEXION
conn = pymysql.connect(host=config['mysql']['user'],
                       user=config['mysql']['password'],
                       password=config['mysql']['host'],
                       database=config['mysql']['database']
                       )
cursor = conn.cursor()
app = Flask(__name__)
api = Api(app)


class App(Resource):
    def get(self, doc_id, version_code):
        """
        Método GET que devuelve el apk de la aplicacion solicidada
        :param doc_id:
        :param version_code:
        :return:
        """
        apk = 'Downloads/APKs/' + doc_id + '/' + version_code + '.apk'
        return

    def post(self):
        """
        Método POST para guardar tanto los metadatos en la base de datos como el apk en
        el volumen de Docker
        :return: {status: Aplicación guardada}
        """


class Metadata(Resource):
    def get(self, doc_id, version_code):
        """
        Método GET que devuelve los metadatos de una aplicacion con un vc determinado
        :param doc_id:
        :param version_code:
        :return:
        """
        query = ("SELECT * FROM App " \
                "INNER JOIN Dependencies ON App.docId = Dependencies.app" \
                "INNER JOIN Files ON App.docId = Files.app" \
                "INNER JOIN Offers ON App.docId = Offers.app" \
                "INNER JOIN Permissions ON App.docId = Permissions.app" \
                "WHERE docId = '%s' and versionCode = %s", doc_id, version_code)
        result = cursor.execute(query)
        return result

    def post(self):
        """
        Método POST para guardar tanto los metadatos en la base de datos como el apk en
        el volumen de Docker
        :return: {status: Aplicación guardada}
        """


class PrivacyPolicy(Resource):
    def get(self):
        """

        :return:
        """

    def post(self):
        """
        Método POST para guardar tanto los metadatos en la base de datos como el apk en
        el volumen de Docker
        :return: {status: Aplicación guardada}
        """


api.add_resource(App, 'App/<doc_id>/<version_code>')
api.add_resource(Metadata, 'Metadata/<doc_id>/<version_code>')
api.add_resource(PrivacyPolicy, '/PrivacyPolicy/<app_id>')

if __name__ == '__main__':
    app.run(port=3000)
