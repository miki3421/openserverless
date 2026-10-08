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

"""Start the unmodified deployed legacy image inside the isolated candidates lab."""
import json
import base64
import subprocess
K=["sudo","-n","k3s","kubectl"]
NS="ops-ferretdb2-lab"
nodes=json.loads(subprocess.check_output(K+["get","nodes","-o","json"]))
assert [n["metadata"]["name"] for n in nodes["items"]]==["ops-advanced-rc7"]
auth=json.loads(subprocess.check_output(K+["get","secret","lab-auth","-n",NS,"-o","json"]))
auth["data"]["LEGACY_URL"]=base64.b64encode(base64.b64decode(auth["data"]["FERRET_URL"]).decode().rsplit("/",1)[0].encode()).decode()
subprocess.run(K+["replace","-f","-"],input=json.dumps(auth).encode(),check=True,stdout=subprocess.DEVNULL)
objects=[{"apiVersion":"apps/v1","kind":"Deployment","metadata":{"name":"legacy16","namespace":NS},"spec":{"replicas":1,"selector":{"matchLabels":{"app":"legacy16"}},"template":{"metadata":{"labels":{"app":"legacy16"}},"spec":{"securityContext":{"fsGroup":1001},"volumes":[{"name":"state","emptyDir":{}}],"containers":[{"name":"legacy16","image":"ghcr.io/nuvolaris/ferretdb:1.6.0","imagePullPolicy":"Never","volumeMounts":[{"name":"state","mountPath":"/state"}],"env":[{"name":"FERRETDB_POSTGRESQL_URL","valueFrom":{"secretKeyRef":{"name":"lab-auth","key":"LEGACY_URL"}}},{"name":"FERRETDB_TELEMETRY","value":"disable"}],"readinessProbe":{"tcpSocket":{"port":27017},"periodSeconds":3}}]}}}}, {"apiVersion":"v1","kind":"Service","metadata":{"name":"legacy16","namespace":NS},"spec":{"selector":{"app":"legacy16"},"ports":[{"port":27017,"targetPort":27017}]}}]
subprocess.run(K+["apply","-f","-"],input=json.dumps({"apiVersion":"v1","kind":"List","items":objects}).encode(),check=True)
