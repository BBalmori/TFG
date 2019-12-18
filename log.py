#! /bin/user/python3
import logging as log
from pythonjsonlogger import jsonlogger

def init_logger(file):
	handler = log.FileHandler(file)
	format_str = '%(levelname)s%(asctime)s%(filename)s%(funcName)s%(lineno)d%(message)'
	formatter = jsonlogger.JsonFormatter(format_str)
	handler.setFormatter(formatter)
	logger = log.getLogger()
	logger.addHandler(handler)
	logger.setLevel(log.INFO)
	return logger
