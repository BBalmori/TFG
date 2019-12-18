import configparser
import os

from login import parse_config_l
from send import send

USER_NAME = None
PASSWORD = None
SERVER_IP = None
QUEUE = None


def main():
    search()


def search():
    parse_config_s('config.config')
    print('\nBROWSE CATEGORIES\n')
    server = parse_config_l('config.config')
    browseList = server.browse()
    for b in browseList:
        catId = b['catId']
        print('\nBUSCANDO SUBCATEGORIAS DE %s\n' % catId)
        catList = server.list(catId)
        for c in catList:
            print('\nBUSCANDO APLICACIONES DE %s\n' % c)
            appList = server.listApps(catId, c, 5)
            for app in appList:
                a = app['docId']
                print('\nENVIO %s A LA COLA\n' % a)
                send(USER_NAME, PASSWORD, SERVER_IP, QUEUE, a)


def parse_config_s(config_file):
    global USER_NAME, PASSWORD, SERVER_IP, QUEUE

    assert os.path.isfile(config_file), '%s is not a valid file or path to file' % config_file

    config = configparser.ConfigParser()
    config.read(config_file)

    assert 'username' in config['rabbitmq'], 'Config file %s does not have an User value' % config_file
    assert 'password' in config['rabbitmq'], 'Config file %s does not have a Password value' % config_file
    assert 'server_ip' in config['rabbitmq'], 'Config file %s does not have a Server IP value' % config_file
    assert 'queue' in config['rabbitmq'], 'Config file %s does not have a Queue value' % config_file
    USER_NAME = config['rabbitmq']['username']
    print('\n %s \n' % USER_NAME)

    PASSWORD = config['rabbitmq']['password']
    print('\n %s \n' % PASSWORD)

    SERVER_IP = config['rabbitmq']['server_ip']
    print('\n %s \n' % SERVER_IP)

    QUEUE = config['rabbitmq']['queue']
    print('\n %s \n' % QUEUE)


if __name__ == "__main__":
    main()
