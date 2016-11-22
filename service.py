# -*- coding: utf-8 -*-
from __future__ import print_function
import os
from logging.handlers import RotatingFileHandler

import flask
from flask import Flask, request, abort
import logging

import common
import constants
from common import download_queue
import config
from common import sogou_api
from response_body import get_success_response, get_error_response, ResponseBody
from storage.sqlite_storage import SQLiteStorage

app = Flask(__name__)

if not os.path.exists(config.local_storage_path):
    os.makedirs(config.local_storage_path)

if not os.path.exists(config.db_path):
    os.makedirs(config.local_storage_path)

if not os.path.exists(config.log_path):
    os.makedirs(config.log_path)


sqlite_helper = SQLiteStorage()


@app.before_request
def reject_head_request():
    if request.method == 'HEAD':
        abort(400)


@app.errorhandler(404)
def page_not_found(e):
    return get_error_response(e.message, should_print=False).format(), 404


@app.route('/')
def homepage():
    return 'HP'


@app.route('/rest/name/<account_name>')
def search_account_by_name(account_name):
    account_name = account_name.encode('UTF-8')
    api = sogou_api.get_wx_api()
    result = api.search_gzh_info(account_name)
    return flask.jsonify(result)


@app.route('/rest/id/<account_id>')
def search_account_by_id(account_id):
    account_id = account_id.encode('UTF-8')
    api = sogou_api.get_wx_api()
    result = api.search_gzh_info(account_id)
    return flask.jsonify(result)


@app.route('/rest/article/search/<keywords>')
def search_article_by_keywords(keywords):
    keywords = keywords.encode('UTF-8')
    api = sogou_api.get_wx_api()
    result = api.search_article_info(keywords)
    return flask.jsonify(result)


@app.route('/rest/message/<account_id>')
def search_message_by_id(account_id):
    account_id = account_id.encode('UTF-8')
    api = sogou_api.get_wx_api()
    result = api.get_gzh_message(wechatid=account_id)
    return flask.jsonify(result)


@app.route('/rest/article/all/<account_id>')
def list_all_articles_by_id(account_id):
    return flask.jsonify(sogou_api.get_articles_by_id(account_id))


@app.route('/rest/wxid/add/<wxid>')
def add_wxid(wxid):
    try:
        sqlite_helper.subscribe(wxid)
        return get_success_response().format()
    except Exception as e:
        return get_error_response(e.message).format()


@app.route('/rest/status')
def get_status():
    return ResponseBody(1, download_queue.get_status()).format()


@app.route('/start')
def start():
    return get_success_response().format() if download_queue.start() else get_error_response('spider is running').format()


@app.route('/rest/progress')
def progress():
    if download_queue.get_status() == constants.BUSY:
        p = download_queue.get_thread_progress()
        return ResponseBody(**p).format()
    if download_queue.get_status() == constants.IDLE:
        return ResponseBody(total=0, progress=-1, sub_task_total=0, sub_task_progress=-1).format()


@app.route('/rest/log/<line>')
def get_log(line):
    if not line:
        line = 0
    l = download_queue.get_log_from(line)
    return ResponseBody(log=l).format()


@app.route('/rest/article/date/written/<date>')
def get_articles_by_date_written(date):
    if not common.valid_date_string(date):
        return get_error_response('%s is not a date' % date).format()
    articles = sqlite_helper.get_articles_by_date_written(date)
    return ResponseBody(articles=articles).format()


@app.route('/rest/article/date/create_at/<date>')
def get_articles_by_date_created(date):
    if not common.valid_date_string(date):
        return get_error_response('%s is not a date' % date).format()
    articles = sqlite_helper.get_articles_by_date_created(date)
    return ResponseBody(articles=articles).format()


@app.route('/save')
def save_page():
    subscribes = sqlite_helper.get_wxid_list()
    print(subscribes)
    try:
        info_list = list()
        for s in subscribes:
            print("processing wxid=%s" % s['name'])
            all_articles = sogou_api.get_articles_by_id(s['name'])
            for a in all_articles:
                info_list.append(a)
            download_queue.resolve(info_list)
        return get_success_response().format()
    except Exception as e:
        return get_error_response(e.message).format()


@app.route('/clean')
def clean_cache_and_db():
    pass


def _get_log_path():
    return config.log_path + common.get_time() + '_flask.log'


if __name__ == '__main__':
    handler = RotatingFileHandler(_get_log_path(), maxBytes=100000, backupCount=1)
    handler.setLevel(logging.DEBUG)
    app.logger.addHandler(handler)
    app.run(port=config.http_port)
