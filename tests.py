import unittest
import json
import time
import requests

class TestRaftClusterIntegration(unittest.TestCase):

    def setUp(self):
        self.servers = {
            1: "http://raft-server-1:5001",
            2: "http://raft-server-2:5002",
            3: "http://raft-server-3:5003",
            4: "http://raft-server-4:5004"
        }

        time.sleep(2)  # ждем, чтобы все серверы запустились

    def test_put_and_get_data_across_servers(self):
        payload = {
            "key": "foo",
            "value": "bar"
        }
        response = requests.put(f"{self.servers[1]}/put_data", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

        time.sleep(2)

        for server in [2, 3, 4]:
            response = requests.get(f"{self.servers[server]}/get_data", json={"key": "foo"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["value"], "bar")

    def test_server_shutdown_and_recovery(self):
        requests.get(f"{self.servers[2]}/turnoff")
        time.sleep(1)

        payload = {
            "key": "foo",
            "value": "bar"
        }
        response = requests.put(f"{self.servers[2]}/put_data", json=payload)

        response = requests.put(f"{self.servers[1]}/put_data", json=payload)
        self.assertEqual(response.status_code, 200)

        for server in [3, 4]:
            response = requests.get(f"{self.servers[server]}/get_data", json={"key": "foo"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["value"], "bar")

        requests.get(f"{self.servers[2]}/turnon")
        time.sleep(2)

        response = requests.get(f"{self.servers[2]}/get_data", json={"key": "foo"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["value"], "bar")

    def test_election_and_leader_change(self):
        payload = {
            "key": "foo",
            "value": "bar"
        }
        response = requests.put(f"{self.servers[1]}/put_data", json=payload)
        self.assertEqual(response.status_code, 200)

        requests.get(f"{self.servers[1]}/turnoff")
        time.sleep(2)

        for server in [2, 3, 4]:
            response = requests.get(f"{self.servers[server]}/get_data", json={"key": "foo"})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["value"], "bar")

        requests.get(f"{self.servers[1]}/turnon")
        time.sleep(2)

        response = requests.get(f"{self.servers[1]}/get_data", json={"key": "foo"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["value"], "bar")

    def test_failover_and_recovery(self):
        requests.get(f"{self.servers[3]}/turnoff")
        time.sleep(1)

        payload = {
            "key": "foo",
            "value": "bar"
        }
        response = requests.put(f"{self.servers[1]}/put_data", json=payload)
        self.assertEqual(response.status_code, 200)

        response = requests.get(f"{self.servers[2]}/get_data", json={"key": "foo"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["value"], "bar")

        response = requests.get(f"{self.servers[4]}/get_data", json={"key": "foo"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["value"], "bar")

        requests.get(f"{self.servers[3]}/turnon")
        time.sleep(2)

        response = requests.get(f"{self.servers[3]}/get_data", json={"key": "foo"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["value"], "bar")


if __name__ == "__main__":
    unittest.main()
