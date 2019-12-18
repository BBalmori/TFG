import pickle
from gpapi.googleplay import GooglePlayAPI
import configparser
import os

USER = None
PASSWORD = None
FIRST_TIME = False


def parse_config_l(config_file):
    global USER, PASSWORD, FIRST_TIME

    assert os.path.isfile(config_file), '%s is not a valid file or path to file' % config_file

    config = configparser.ConfigParser()
    config.read(config_file)

    assert 'user' in config['login'], 'Config file %s does not have an User value in the sdk section' % config_file
    assert 'password' in config['login'], 'Config file %s does not have a Password value in the  section' % config_file
    assert 'first_time' in config['login'], 'Config file %s does not have a FT value in the section' % config_file
    USER = config['login']['user']
    print('\n %s \n' % USER)

    PASSWORD = config['login']['password']
    print('\n %s \n' % PASSWORD)

    FIRST_TIME = config['login']['first_time']
    print('\n %s \n' % FIRST_TIME)

    server = GooglePlayAPI('es_ES', 'Europe/Spain')

    if FIRST_TIME is True:
        print('\nLogging in with email and password\n')
        server.login(USER, PASSWORD, None, None)
        gsfId = server.gsfId
        print(gsfId)

        authSubToken = server.authSubToken
        print(authSubToken)

        with open('server.pkl', 'wb') as f:
            pickle.dump(server, f, pickle.HIGHEST_PROTOCOL)

    with open('server.pkl', 'rb') as f:
        server = pickle.load(f)

    gsfId = server.gsfId
    print(gsfId)

    authSubToken = server.authSubToken
    print(authSubToken)

    print('\nNow trying secondary login with ac2dm token and gsfId saved\n')
    server = GooglePlayAPI('es_ES', 'Europe/Spain')
    server.login(None, None, gsfId, authSubToken)
    return server

