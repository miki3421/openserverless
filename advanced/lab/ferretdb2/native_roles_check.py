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

"""Check actual custom-role enforcement, including explicit success prerequisites."""
import json
import os
import sys
from pymongo import MongoClient
from pymongo.errors import OperationFailure

def client(user, password):
    return MongoClient("native18", 10260, username=user, password=password,
                       authSource="admin", authMechanism="SCRAM-SHA-256",
                       tls=True, tlsAllowInvalidCertificates=True, directConnection=True,
                       retryWrites=False, serverSelectionTimeoutMS=10000, socketTimeoutMS=20000)
statuses = []
def emit(test, status, **details):
    statuses.append(status)
    print(json.dumps({"test":test,"status":status,**details},default=str),flush=True)
def info(exc):
    text = str(exc)
    for key, value in os.environ.items():
        if "PASSWORD" in key and value:
            text = text.replace(value, "[redacted]")
    return {"type":type(exc).__name__, "code":getattr(exc,"code",None), "message":text[:500]}

admin = client("lab_admin", os.environ["NATIVE_PASSWORD"])
for collection in ["", "synthetic"]:
    label = "wildcard" if not collection else "exact"
    role = "custom_" + label
    try:
        admin.admin.command("createRole", role, privileges=[{"resource":{"db":"custom_alpha_ferretdb", "collection":collection}, "actions":["find","insert","update","remove"]}], roles=[])
        emit(role + "_create", "PASS")
        admin.admin.command("createUser", role + "_user", pwd=os.environ["ALPHA_PASSWORD"], roles=[{"role":role,"db":"admin"}])
        emit(role + "_user_create", "PASS")
    except Exception as exc:
        emit(role + "_create", "UNSUPPORTED", **info(exc))
        continue
    for db in ["custom_alpha_ferretdb", "custom_beta_ferretdb"]:
        admin[db].synthetic.replace_one({"_id":1}, {"_id":1,"owner":db},upsert=True)
    tenant = client(role + "_user", os.environ["ALPHA_PASSWORD"])
    own_success = False
    try:
        assert tenant.custom_alpha_ferretdb.synthetic.find_one({"_id":1})["owner"] == "custom_alpha_ferretdb"
        assert tenant.custom_alpha_ferretdb.synthetic.update_one({"_id":1},{"$set":{"value":5}}).matched_count == 1
        tenant.custom_alpha_ferretdb.synthetic.insert_one({"_id":label})
        assert tenant.custom_alpha_ferretdb.synthetic.delete_one({"_id":label}).deleted_count == 1
        emit(role + "_own_crud", "PASS")
        own_success = True
    except Exception as exc:
        emit(role + "_own_crud", "FAIL", **info(exc))
    if own_success:
        for op, fn in [("read",lambda:tenant.custom_beta_ferretdb.synthetic.find_one({"_id":1})),("write",lambda:str(tenant.custom_beta_ferretdb.synthetic.insert_one({"_id":"intruder"+label}).inserted_id))]:
            try:
                emit(role + "_cross_" + op, "SECURITY_FAIL", result=fn())
            except OperationFailure as exc:
                emit(role + "_cross_" + op, "PASS" if exc.code==13 else "INCONCLUSIVE", **info(exc))
            except Exception as exc:
                emit(role + "_cross_" + op, "INCONCLUSIVE", **info(exc))
    else:
        emit(role + "_isolation", "UNVALIDATED", reason="own CRUD is not functional")
    tenant.close()
admin.close()
sys.exit(2 if any(status != "PASS" for status in statuses) else 0)
