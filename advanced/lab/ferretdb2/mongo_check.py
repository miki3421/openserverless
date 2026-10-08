# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the License for the
# specific language governing permissions and limitations
# under the License.

"""Synthetic compatibility and tenant isolation probes, for this VM lab only.

Logs contain no credentials. A negative authorization result only counts when
the same user successfully performs its own CRUD and the peer fixture exists.
"""
import json
import os
import time
import sys
from pymongo import MongoClient
from pymongo.errors import OperationFailure

MODE = os.environ["MODE"]
HOST = {"ferret": "ferret27", "native": "native18", "ferret18": "native18"}[MODE]
PORT = 10260 if MODE == "native" else 27017
report = []
def emit(name, status, **extra):
    item = {"test": name, "status": status, **extra}
    report.append(item)
    print(json.dumps(item, default=str), flush=True)
def error(exc):
    message = str(exc)
    for key, value in os.environ.items():
        if "PASSWORD" in key and value:
            message = message.replace(value, "[redacted]")
    return {"type": type(exc).__name__, "code": getattr(exc, "code", None), "message": message[:500]}
def connect(user=None, password=None, **extra):
    options = dict(host=HOST, port=PORT, serverSelectionTimeoutMS=15000, connectTimeoutMS=10000,
                   socketTimeoutMS=20000, directConnection=True, retryWrites=False, **extra)
    if user:
        options.update(username=user, password=password, authSource="admin", authMechanism="SCRAM-SHA-256")
    if MODE == "native":
        # Self-signed certificate accepted only inside this internal synthetic lab.
        options.update(tls=True, tlsAllowInvalidCertificates=True)
    return MongoClient(**options)
admin = connect("postgres" if MODE == "ferret" else "lab_admin", os.environ["PG_PASSWORD" if MODE == "ferret" else "NATIVE_PASSWORD"])
for attempt in range(24):
    try:
        info = admin.admin.command("buildInfo")
        emit("buildInfo", "PASS", version=info.get("version"), extensions=info.get("documentdb"))
        break
    except Exception as exc:
        if attempt == 23:
            emit("admin_authentication", "FAIL", **error(exc))
            sys.exit(1)
        time.sleep(5)

def denial(name, fn):
    try:
        result = fn()
        emit(name, "SECURITY_FAIL", reason="operation succeeded", result=result)
        return False
    except OperationFailure as exc:
        if exc.code == 13:
            emit(name, "PASS", code=13)
            return True
        emit(name, "INCONCLUSIVE", **error(exc))
        return False
    except Exception as exc:
        emit(name, "INCONCLUSIVE", **error(exc))
        return False

def tenant_pair(prefix, scoped):
    clients = []
    for label in ["alpha", "beta"]:
        user = f"{prefix}_{label}"
        dbname = f"{prefix}_{label}_ferretdb"
        roles = [{"role": "readWrite", "db": dbname}] if scoped else []
        password = os.environ[label.upper() + "_PASSWORD"]
        try:
            admin.admin.command("createUser", user, pwd=password, roles=roles)
            emit(user + "_create", "PASS", roles=roles)
        except Exception as exc:
            emit(user + "_create", "UNSUPPORTED", **error(exc))
            return
        clients.append((user, dbname, connect(user, password)))
    for user, dbname, client in clients:
        try:
            coll = client[dbname]["synthetic"]
            coll.insert_many([{"_id": 1, "owner": user, "value": 3}, {"_id": 2, "owner": user, "value": 7}])
            assert coll.find_one({"_id": 1})["owner"] == user
            assert coll.update_one({"_id": 1}, {"$inc": {"value": 1}}).modified_count == 1
            coll.create_index("value")
            value = list(coll.aggregate([{"$group": {"_id": None, "sum": {"$sum": "$value"}}}]))
            assert value[0]["sum"] == 11
            assert coll.delete_one({"_id": 2}).deleted_count == 1
            emit(user + "_own_crud_index_aggregate", "PASS")
        except Exception as exc:
            emit(user + "_own_crud_index_aggregate", "FAIL", **error(exc))
            return  # Cross checks without successful fixtures would be misleading.
    for i, (user, dbname, client) in enumerate(clients):
        peerdb = clients[1-i][1]
        denial(user + "_cross_read", lambda: client[peerdb]["synthetic"].find_one({"_id": 1}))
        denial(user + "_cross_write", lambda: str(client[peerdb]["synthetic"].insert_one({"_id": f"intruder-{user}"}).inserted_id))
        denial(user + "_cross_update", lambda: client[peerdb]["synthetic"].update_one({"_id": 1}, {"$set": {"intruded": True}}).modified_count)
        denial(user + "_create_admin", lambda: client.admin.command("createUser", "intruder_" + user, pwd=os.environ["ALPHA_PASSWORD"], roles=[{"role":"root","db":"admin"}]))
        denial(user + "_list_peer_collections", lambda: client[peerdb].list_collection_names())
        denial(user + "_cross_drop", lambda: client[peerdb].command("drop", "synthetic"))
    for _, _, client in clients:
        client.close()

tenant_pair("scoped", True)
if MODE in ("ferret", "ferret18"):
    tenant_pair("default", False)
fixture = admin["authentication_probe_" + MODE]["synthetic"]
fixture.insert_one({"_id": 1, "value": "private"})
for name, client in [("anonymous", connect()), ("wrong_password", connect("postgres" if MODE == "ferret" else "lab_admin", "intentionally-wrong-password"))]:
    try:
        client["authentication_probe_" + MODE]["synthetic"].find_one({"_id": 1})
        emit(name, "SECURITY_FAIL", reason="private data readable")
    except OperationFailure as exc:
        emit(name, "PASS" if exc.code in (13, 18) else "INCONCLUSIVE", **error(exc))
    except Exception as exc:
        emit(name, "INCONCLUSIVE", **error(exc))
    finally:
        client.close()
admin.close()
emit("summary", "RECORDED", mode=MODE, counts={s:sum(x["status"]==s for x in report) for s in sorted({x["status"] for x in report})})
sys.exit(2 if any(r["status"] in ("SECURITY_FAIL", "FAIL", "INCONCLUSIVE", "UNSUPPORTED") for r in report) else 0)
