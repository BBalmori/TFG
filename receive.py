#!/usr/bin/env python
import configparser
import os

import pika
from download import download
from login import parse_config_l
from metadata import metadata
from privacypolicy import downloadPolicy

USER_NAME = None
PASSWORD = None
SERVER_IP = None
QUEUE = None


def main():
    parse_config_r('config.config')
    receive()


def testing(ch, method, properties, body):
    print(" [x] Received %r" % body)
    ch.basic_ack(delivery_tag=method.delivery_tag)
    server = parse_config_l('config.config')
    download(server, body)
    metadata(server, body)
    downloadPolicy(server, body)


def receive():
    credentials = pika.PlainCredentials(username=USER_NAME, password=PASSWORD)
    connection = pika.BlockingConnection(pika.ConnectionParameters(SERVER_IP, 5672, '/', credentials=credentials))
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE)
    channel.basic_consume(queue=QUEUE, on_message_callback=testing)
    print(' [*] Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()


def parse_config_r(config_file):
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
