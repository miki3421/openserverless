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

"""Reproduce OPS SQL tenant grants; test whether the Mongo gateway respects them."""
import json
import os
import sys
from pg8000.native import Connection
from pymongo import MongoClient
from pymongo.errors import OperationFailure

def emit(name, status, **extra):
    print(json.dumps({"test":name,"status":status,**extra},default=str),flush=True)
def pg(user, password, database):
    return Connection(user=user,password=password,database=database,host="pg17-docdb",port=5432,timeout=15)
root = pg("postgres", os.environ["PG_PASSWORD"], "postgres")
for label in ["alpha", "beta"]:
    db = "sql_" + label + "_ferretdb"
    password = os.environ[label.upper()+"_PASSWORD"]
    root.run(f"CREATE DATABASE {db}")
    root.run(f"CREATE ROLE {db} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{password}'")
    root.run(f"GRANT ALL PRIVILEGES ON DATABASE {db} TO {db}")
    root.run(f"REVOKE CONNECT ON DATABASE {db} FROM PUBLIC")
    own = pg(db,password,db)
    assert own.run("SELECT current_database(), current_user")[0] == [db,db]
    emit(db + "_sql_own", "PASS")
    own.close()
root.run("REVOKE CONNECT ON DATABASE postgres FROM PUBLIC")
clients=[]
for label in ["alpha", "beta"]:
    db="sql_" + label + "_ferretdb"
    peer="sql_" + ("beta" if label=="alpha" else "alpha") + "_ferretdb"
    password=os.environ[label.upper()+"_PASSWORD"]
    for target in [peer,"postgres"]:
        try:
            c=pg(db,password,target)
            c.close()
            emit(db + "_sql_deny_" + target,"SECURITY_FAIL")
        except Exception as exc:
            state=exc.args[0].get("C") if exc.args and isinstance(exc.args[0],dict) else None
            emit(db + "_sql_deny_" + target,"PASS" if state=="42501" else "INCONCLUSIVE",sqlstate=state)
    c=MongoClient("ferret27",27017,username=db,password=password,authSource="admin",authMechanism="SCRAM-SHA-256",directConnection=True,retryWrites=False,serverSelectionTimeoutMS=10000,socketTimeoutMS=15000)
    c[db].synthetic.insert_one({"_id":1,"owner":label})
    assert c[db].synthetic.find_one({"_id":1})["owner"]==label
    emit(db + "_mongo_own_crud","PASS")
    clients.append((db,peer,c))
failures=0
for db,peer,c in clients:
    for op,fn in [("read",lambda:c[peer].synthetic.find_one({"_id":1})),("write",lambda:str(c[peer].synthetic.insert_one({"_id":"intruder-"+db}).inserted_id))]:
        try:
            result=fn()
            emit(db + "_mongo_cross_" + op,"SECURITY_FAIL",result=result)
            failures+=1
        except OperationFailure as exc:
            emit(db + "_mongo_cross_" + op,"PASS" if exc.code==13 else "INCONCLUSIVE",code=exc.code)
    c.close()
legacy=MongoClient("ferret27",27017,username="sql_alpha_ferretdb",password=os.environ["ALPHA_PASSWORD"],authSource="admin",authMechanism="PLAIN",directConnection=True,retryWrites=False,serverSelectionTimeoutMS=10000,socketTimeoutMS=15000)
try:
    legacy.sql_alpha_ferretdb.synthetic.find_one({"_id":1})
    emit("legacy_PLAIN","UNEXPECTEDLY_ACCEPTED")
except OperationFailure as exc:
    emit("legacy_PLAIN","INCOMPATIBLE",code=exc.code)
finally:
    legacy.close()
emit("sql_backend_routing","RECORDED",logical_tenant_storage=root.run("SELECT database_name,collection_name FROM documentdb_api_catalog.collections WHERE database_name IN ('sql_alpha_ferretdb','sql_beta_ferretdb') ORDER BY database_name"))
root.close()
sys.exit(2 if failures else 0)
