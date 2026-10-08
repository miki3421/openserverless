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

"""Isolated CouchDB compatibility probe on the retained Advanced VM."""
import base64
import json
import pathlib
import secrets
import socket
import subprocess

assert socket.gethostname() == "ops-advanced-rc7"
NS = "ops-couchdb3-settings-lab"
KUBE = ["sudo","-n","k3s","kubectl"]
IMAGE = "docker.io/apache/couchdb:3.5.2@sha256:c703989c0a370a1a6b179785bcb5b2b5501347bb0219d02d597d0a9107eb8d28"

SETTINGS = '[couchdb]\nsingle_node = true\n[cluster]\nn = 1\n[query_server_config]\nreduce_limit = false\n[compactions]\nopenserverless_activations = [{db_fragmentation, "60%"}, {view_fragmentation, "60%"}]\nopenserverless_subjects = [{db_fragmentation, "60%"}, {view_fragmentation, "60%"}]\nopenserverless_whisks = [{db_fragmentation, "60%"}, {view_fragmentation, "60%"}]\n'

def apply(obj):
    subprocess.run(KUBE+["apply","-f","-"],input=json.dumps(obj),text=True,check=True,stdout=subprocess.DEVNULL)

existing=subprocess.check_output(KUBE+["get","namespace",NS,"--ignore-not-found","-o","json"],text=True)
if existing.strip(): raise RuntimeError("Probe namespace already exists; use a fresh isolated namespace instead of rotating its credentials implicitly")

credentials={"ADMIN_USER":"probe_admin","ADMIN_PASSWORD":secrets.token_hex(24),"CTRL_PASSWORD":secrets.token_hex(24),"INVOKER_PASSWORD":secrets.token_hex(24)}
apply({"apiVersion":"v1","kind":"Namespace","metadata":{"name":NS}})
apply({"apiVersion":"v1","kind":"Secret","metadata":{"name":"couchdb-probe-auth","namespace":NS},"stringData":credentials})
ref=lambda key:{"secretKeyRef":{"name":"couchdb-probe-auth","key":key}}
apply({"apiVersion":"v1","kind":"Service","metadata":{"name":"couchdb3","namespace":NS},"spec":{"selector":{"app":"couchdb3-probe"},"ports":[{"port":5984,"targetPort":5984}]}})
statefulset = {"apiVersion":"apps/v1","kind":"StatefulSet","metadata":{"name":"couchdb3","namespace":NS},"spec":{"serviceName":"couchdb3","replicas":1,"selector":{"matchLabels":{"app":"couchdb3-probe"}},"template":{"metadata":{"labels":{"app":"couchdb3-probe"}},"spec":{"automountServiceAccountToken":False,"containers":[{"name":"couchdb","image":IMAGE,"env":[{"name":"COUCHDB_USER","valueFrom":ref("ADMIN_USER")},{"name":"COUCHDB_PASSWORD","valueFrom":ref("ADMIN_PASSWORD")}],"ports":[{"containerPort":5984}],"readinessProbe":{"tcpSocket":{"port":5984},"initialDelaySeconds":5,"periodSeconds":5},"resources":{"requests":{"cpu":"100m","memory":"128Mi"},"limits":{"cpu":"1","memory":"1Gi"}},"volumeMounts":[{"name":"data","mountPath":"/opt/couchdb/data"}]}]}},"volumeClaimTemplates":[{"metadata":{"name":"data"},"spec":{"accessModes":["ReadWriteOnce"],"storageClassName":"local-path","resources":{"requests":{"storage":"1Gi"}}}}]}}
apply({"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"couchdb-settings","namespace":NS},"data":{"00-openserverless.ini":SETTINGS}})
container=statefulset["spec"]["template"]["spec"]["containers"][0]
container["command"]=["sh","-c"]
container["args"]=["cp /lab-config/00-openserverless.ini /opt/couchdb/etc/local.d/00-openserverless.ini || exit 1; exec tini -- /docker-entrypoint.sh /opt/couchdb/bin/couchdb"]
container["volumeMounts"].append({"name":"settings","mountPath":"/lab-config","readOnly":True})
statefulset["spec"]["template"]["spec"]["volumes"]=[{"name":"settings","configMap":{"name":"couchdb-settings"}}]
apply(statefulset)

probe = r'''import json,os,requests
from openserverless import couchdb as couch, couchdb_util, config
config.configure({"couchdb":{"host":"couchdb3.ops-couchdb3-settings-lab.svc.cluster.local","admin":{"user":os.environ["ADMIN_USER"],"password":os.environ["ADMIN_PASSWORD"]},"controller":{"user":"controller_admin","password":os.environ["CTRL_PASSWORD"]},"invoker":{"user":"invoker_admin","password":os.environ["INVOKER_PASSWORD"]}},"openwhisk":{"namespaces":{"openserverless":"probe-uuid:probe-auth-key"}}})
db=couchdb_util.CouchDB()
assert db.wait_db_ready(90)
version=db.db_session.get(db.db_url).json()["version"]
assert version=="3.5.2",version
for name in ["init_system","init_subjects","init_activations","init_actions","add_initial_subjects","init_users_metadata","init_compactions_config"]:
    assert getattr(couch,name)(db),name
views=0
for database in ["subjects","activations","whisks"]:
    docs=db.db_session.get(f"{db.db_base}{database}/_all_docs",params={"startkey":'"_design/"',"endkey":'"_design0"',"include_docs":"true"})
    docs.raise_for_status()
    for row in docs.json()["rows"]:
        document=row["doc"]
        for view in document.get("views",{}):
            response=db.db_session.get(f"{db.db_base}{database}/{document['_id']}/_view/{view}",params={"reduce":"false","limit":1})
            assert response.status_code==200,(database,view,response.status_code)
            views+=1
assert views>0
assert db.create_db("probe")
assert db.update_doc("probe",{"_id":"crud","sequence":1})
assert db.update_doc("probe",{"_id":"crud","sequence":2})
assert db.get_doc("probe","crud")["sequence"]==2
assert db.delete_doc("probe","crud")
assert db.get_doc("probe","crud") is None
assert db.update_doc("probe",{"_id":"restart-probe","value":"persist-after-restart"})
assert requests.get(f"{db.db_base}subjects").status_code==401
assert requests.get(f"{db.db_base}subjects",auth=(os.environ["ADMIN_USER"],"wrong-password")).status_code==401
for username,key in [("controller_admin","CTRL_PASSWORD"),("invoker_admin","INVOKER_PASSWORD")]:
    assert requests.get(f"{db.db_base}subjects",auth=(username,os.environ[key])).status_code==200
assert db.add_user("unrelated_user","synthetic-unrelated-password")
assert requests.get(f"{db.db_base}subjects",auth=("unrelated_user","synthetic-unrelated-password")).status_code==403
print(json.dumps({"version":version,"ops_initialization":True,"design_views_queried":views,"crud":True,"anonymous_denied":True,"wrong_password_denied":True,"service_users_authorized":True,"unrelated_user_denied":True},indent=2))
'''
apply({"apiVersion":"v1","kind":"ConfigMap","metadata":{"name":"couchdb-compatibility-probe","namespace":NS},"data":{"probe.py":probe}})
apply({"apiVersion":"batch/v1","kind":"Job","metadata":{"name":"couchdb-compatibility-probe","namespace":NS},"spec":{"backoffLimit":0,"template":{"spec":{"automountServiceAccountToken":False,"restartPolicy":"Never","containers":[{"name":"probe","image":"docker.io/miki3421/ops-advanced-operator:couchdb35-dev","imagePullPolicy":"IfNotPresent","command":["/home/openserverless/.venv/bin/python","/lab/probe.py"],"env":[{"name":key,"valueFrom":ref(key)} for key in credentials],"volumeMounts":[{"name":"script","mountPath":"/lab","readOnly":True}]}],"volumes":[{"name":"script","configMap":{"name":"couchdb-compatibility-probe"}}]}}}})
print("Isolated CouchDB 3.5.2 probe deployed")
