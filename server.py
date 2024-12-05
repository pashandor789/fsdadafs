import time
import random
import threading
import stat
import difflib
import unittest
import requests
import sys
import os
import socketserver
import logging
from flask import Flask, jsonify, request
from collections import defaultdict
import socket
import subprocess


ELECTION_TIMEOUT_MIN = 4
ELECTION_TIMEOUT_MAX = 10
HEARTBEAT_INTERVAL = 1

SERVER_ID = int(
    os.getenv("SERVER_ID", 1)
)

SERVER_ADDRESSES = {
    1: "http://raft-server-1:5001",
    2: "http://raft-server-2:5002",
    3: "http://raft-server-3:5003",
    4: "http://raft-server-4:5004",
}

logger = logging.getLogger()
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stderr)
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter('%(message)s')
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

###################################################################################
###                                                                             ###
###                                 Raft Server                                 ###
###                                                                             ###
###################################################################################

class RaftServer:
    class ServerState:
        FOLLOWER = "follower"
        LEADER = "leader"

    def __init__(self, server_id: int):
        self.server_id = server_id
        self.state = self.ServerState.FOLLOWER
        self.leader_id = None
        self.last_heartbeat_time = time.time()
        self.term = 0
        self.votes_by_term = dict()
        self.alive = True

        self.change_log = dict()

        self.election_timeout = (
            ELECTION_TIMEOUT_MIN + self.server_id * 3
        )
        self.election_timeout_start_time = time.time()

        self.app = Flask(__name__)
        self.app.add_url_rule(
            "/heartbeat", 
            "heartbeat", 
            self.heartbeat, 
            methods=["POST"]
        )

        self.app.add_url_rule(
            "/vote", 
            "vote", 
            self.vote, 
            methods=["POST"]
        )

        self.app.add_url_rule(
            "/status", 
            "status", 
            self.status, 
            methods=["GET"]
        )

        self.app.add_url_rule(
            "/turnoff", 
            "turnoff", 
            self.turnoff, 
            methods=["GET"]
        )

        self.app.add_url_rule(
            "/turnon", 
            "turnon", 
            self.turnon, 
            methods=["GET"]
        )

        self.app.add_url_rule(
            "/get_data", 
            "get_data", 
            self.get_data, 
            methods=["GET"]
        )

        self.app.add_url_rule(
            "/put_data", 
            "put_data", 
            self.put_data, 
            methods=["PUT"]
        )

        self.app.add_url_rule(
            "/post_data", 
            "post_data", 
            self.post_data, 
            methods=["POST"]
        )

        self.app.add_url_rule(
            "/delete_data", 
            "delete_data", 
            self.delete_data, 
            methods=["DELETE"]
        )

        self.app.add_url_rule(
            "/head_data", 
            "head_data", 
            self.head_data, 
            methods=["HEAD"]
        )

        self.app.add_url_rule(
            "/update_data", 
            "update_data", 
            self.update_data, 
            methods=["PATCH"]
        )


    def get_data(self):
        data = request.get_json()
        key = data.get("key")

        if self.state != self.ServerState.LEADER:
            try:
                response = requests.get(
                    f"{SERVER_ADDRESSES[self.leader_id]}/get_data",
                    json={"key": key},
                    timeout=1
                )
                return jsonify(
                    response.json()
                )
            except requests.RequestException as e:
                return jsonify(
                    {
                        "status": "error", 
                        "message": str(e)
                    }
                )
        else:
            return jsonify(
                {
                    "key": key, 
                    "value": self.change_log.get(key)
                }
            )


    def put_data(self):
        data = request.get_json()
        key = data.get("key")
        value = data.get("value")

        if self.state != self.ServerState.LEADER:
            try:
                response = requests.post(
                    f"{SERVER_ADDRESSES[self.leader_id]}/put_data",
                    json={"key": key, "value": value},
                    timeout=1
                )
                return jsonify(response.json())
            except requests.RequestException as e:
                return jsonify(
                    {
                        "status": "error",
                        "message": str(e)
                    }
                )
        else:
            self.change_log[key] = value
            return jsonify({"status": "ok"})


    def post_data(self):
        data = request.get_json()
        key = data.get("key")
        value = data.get("value")

        if self.state != self.ServerState.LEADER:
            try:
                response = requests.post(
                    f"{SERVER_ADDRESSES[self.leader_id]}/post_data",
                    json={"key": key, "value": value},
                    timeout=1
                )
                return jsonify(
                    response.json()
                )
            except requests.RequestException as e:
                return jsonify(
                    {
                        "status": "error",
                        "message": str(e)
                    }
                )
        else:
            self.change_log[key] = value
            return jsonify({"status": "ok"})


    def delete_data(self):
        data = request.get_json()
        key = data.get("key")

        if self.state != self.ServerState.LEADER:
            try:
                response = requests.delete(
                    f"{SERVER_ADDRESSES[self.leader_id]}/delete_data",
                    json={"key": key},
                    timeout=1
                )
                return jsonify(response.json())
            except requests.RequestException as e:
                return jsonify(
                    {
                        "status": "error", 
                        "message": str(e)
                    }
                )
        else:
            if key in self.change_log:
                del self.change_log[key]
                return jsonify({"status": "ok"})
            return jsonify(
                {
                    "status": "error", 
                    "message": "Key not found"
                }
            )


    def head_data(self):
        data = request.get_json()
        key = data.get("key")

        if self.state != self.ServerState.LEADER:
            try:
                response = requests.head(
                    f"{SERVER_ADDRESSES[self.leader_id]}/head_data",
                    json={
                        "key": key
                    },
                    timeout=1
                )
                return jsonify(response.headers)
            except requests.RequestException as e:
                return jsonify(
                    {
                        "status": "error", 
                        "message": str(e)
                    }
                )
        else:
            if key in self.change_log:
                return jsonify(
                    {
                        "status": "exists"
                    }
                )
            return jsonify(
                {
                    "status": "not found"
                }
            )


    def update_data(self):
        data = request.get_json()
        key = data.get("key")
        value = data.get("value")

        if self.state != self.ServerState.LEADER:
            try:
                response = requests.patch(
                    f"{SERVER_ADDRESSES[self.leader_id]}/update_data",
                    json={
                        "key": key, 
                        "value": value
                    },
                    timeout=1
                )
                return jsonify(response.json())
            except requests.RequestException as e:
                return jsonify(
                    {
                        "status": "error", 
                        "message": str(e)
                    }
                )
        else:
            if key in self.change_log:
                self.change_log[key] = value
                return jsonify(
                    {
                        "status": "ok"
                    }
                )
            return jsonify(
                {
                    "status": "error", 
                    "message": "Key not found"
                }
            )


    def turnon(self):
        self.alive = True
        logger.info(f"is alive now in term: {self.term}")
        return jsonify(
            {
                "status": "ok"
            }
        )


    def turnoff(self):
        self.alive = False
        logger.info(f"is dead now")
        return jsonify(
            {
                "status": "ok"
            }
        )


    def send_heartbeat(self):
        """Отправка heartbeat на все сервера, если сервер является лидером."""
        while True:
            self.deadimitation()

            if self.state == self.ServerState.LEADER:
                for server_id, url in SERVER_ADDRESSES.items():
                    if server_id != self.server_id:
                        try:
                            requests.post(
                                f"{url}/heartbeat",
                                json={
                                    "leader_id": self.server_id,
                                    "term": self.term,
                                    "change_log": self.change_log
                                },
                                timeout=1
                            )
                        except requests.exceptions.RequestException:
                            pass
                self.last_heartbeat_time = time.time()
            time.sleep(HEARTBEAT_INTERVAL)


    def start_election(self):
        """Запуск выборов, если сервер стал кандидатом."""

        votes = 0

        self.term = self.term + 1
        for server_id, url in SERVER_ADDRESSES.items():
            try:
                response = requests.post(
                    f"{url}/vote",
                    json={
                        "candidate_id": self.server_id,
                        "term": self.term
                    },
                    timeout=1
                )
                if response.json().get("vote_granted"):
                    votes += 1
            except requests.exceptions.RequestException as e:
                print(f'SERVER #{server_id} failed: {e}')
                pass

        if votes > len(SERVER_ADDRESSES) // 2:
            self.state = self.ServerState.LEADER
            self.leader_id = self.server_id
            logger.info(f"Server {self.server_id} is elected as leader! КАНДИДАТЫ МОЛОДЦЫ!")

        self.last_heartbeat_time = time.time()


    def election_check(self):
        """Проверка, если не было получено heartbeat, запускаем выборы."""

        while True:
            self.deadimitation()

            if time.time() - self.last_heartbeat_time > self.election_timeout:
                if self.state != self.ServerState.LEADER:
                    logger.info(f"Server {self.server_id} starts ВЫБОРЫ ВЫБОРЫ!")
                    self.start_election()

                self.election_timeout_start_time = time.time()

            self.log_stats()
            time.sleep(1)


    def log_stats(self):
        logger.info(
            f'TERM: {self.term}, ID: {self.server_id}, State: {self.state}, ChangeLog: {self.change_log.items()}'
        )
        return


    def deadimitation(self):
        while not self.alive:
            time.sleep(0.5)


    def heartbeat(self):
        """Обработка входящих heartbeats от лидера."""
        self.deadimitation()

        data = request.get_json()
        leader_id = data.get("leader_id")
        term = data.get("term")

        if self.term > term:
            return jsonify({"status": "bad"})

        if self.term <= term:
            self.state = self.ServerState.FOLLOWER
            self.term = term

        if leader_id is not None:
            self.last_heartbeat_time = time.time()
            self.leader_id = leader_id

        self.change_log = data.get("change_log")

        return jsonify({"status": "ok"})


    def vote(self):
        """Обработка запросов на голосование от кандидатов."""
        self.deadimitation()

        data = request.get_json()
        candidate_id = data.get("candidate_id")
        term = data.get("term")

        if term > self.term:
            self.term = term

        if self.server_id == candidate_id:
            logger.info(f"Server {self.server_id} votes for candidate {candidate_id}")
            return jsonify(
                {
                    "vote_granted": True
                }
            )

        if self.state == self.ServerState.FOLLOWER:
            if term in self.votes_by_term:
                return jsonify({"vote_granted": False})

            self.last_heartbeat_time = time.time()
            self.votes_by_term[term] = candidate_id
            logger.info(f"Server {self.server_id} votes for candidate {candidate_id}")

            return jsonify(
                {
                    "vote_granted": True
                }
            )

        return jsonify(
            {
                "vote_granted": False
            }
        )


    def status(self):
        """Возвращает текущее состояние сервера."""
        return jsonify(
            {
                "state": self.state,
                "leader_id": self.leader_id,
                "term": self.term
            }
        )


    def run(self):
        """Запуск Flask сервера и потоков для выборов и heartbeat."""

        threading.Thread(
            target=self.send_heartbeat, 
            daemon=True
        ).start()

        threading.Thread(
            target=self.election_check, 
            daemon=True
        ).start()

        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)

        self.app.run(
            host="0.0.0.0", 
            port=5000 + self.server_id, 
            threaded=True
        )


if __name__ == "__main__":
    print(
        'SERVER IS STARTING', 
        file=sys.stderr
    )
    raft_server = RaftServer(SERVER_ID)
    raft_server.run()
