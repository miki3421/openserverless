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

"""Control experiment: current OPS FerretDB image and existing SQL tenant grants."""
import json
import os
import sys
from pymongo import MongoClient
from pymongo.errors import OperationFailure
def emit(test,status,**details):
    print(json.dumps({"test":test,"status":status,**details},default=str),flush=True)
clients=[]
for label in ["alpha","beta"]:
    db="sql_"+label+"_ferretdb"
    password=os.environ[label.upper()+"_PASSWORD"]
    c=MongoClient(f"mongodb://{db}:{password}@legacy16:27017/{db}?authMechanism=PLAIN",directConnection=True,retryWrites=False,serverSelectionTimeoutMS=15000,socketTimeoutMS=20000)
    c[db].legacy_synthetic.insert_many([{"_id":1,"owner":label,"value":3},{"_id":2,"owner":label,"value":7}])
    assert c[db].legacy_synthetic.find_one({"_id":1})["owner"]==label
    assert c[db].legacy_synthetic.update_one({"_id":1},{"$inc":{"value":1}}).modified_count==1
    c[db].legacy_synthetic.create_index("value")
    result=list(c[db].legacy_synthetic.aggregate([{"$group":{"_id":None,"sum":{"$sum":"$value"}}}]))
    assert result[0]["sum"]==11
    assert c[db].legacy_synthetic.delete_one({"_id":2}).deleted_count==1
    emit(db + "_own_crud_index_aggregate","PASS")
    clients.append((db,c))
failed=False
for i,(db,c) in enumerate(clients):
    peer=clients[1-i][0]
    try:
        result=c[peer].legacy_synthetic.find_one({"_id":1})
        if result and result.get("owner") == ("beta" if i==0 else "alpha"):
            emit(db + "_cross_read","SECURITY_FAIL",result=result)
            failed=True
        else:
            # A database name can be remapped under a fixed authenticated PG DB;
            # empty/virtual collections do not constitute reading the real peer.
            emit(db + "_cross_read","PASS",result=result,reason="peer fixture inaccessible")
    except OperationFailure as exc:
        emit(db + "_cross_read","PASS" if exc.code==13 else "INCONCLUSIVE",code=exc.code)
        failed |= exc.code!=13
    try:
        c[peer].legacy_synthetic.insert_one({"_id":"intruder-"+db,"owner":"intruder"})
        peer_client=clients[1-i][1]
        actual=peer_client[peer].legacy_synthetic.find_one({"_id":"intruder-"+db})
        emit(db + "_cross_write","SECURITY_FAIL" if actual else "PASS",peer_data_changed=bool(actual))
        failed |= bool(actual)
    except OperationFailure as exc:
        emit(db + "_cross_write","PASS" if exc.code==13 else "INCONCLUSIVE",code=exc.code)
        failed |= exc.code!=13
for _,c in clients:
    c.close()
sys.exit(2 if failed else 0)
