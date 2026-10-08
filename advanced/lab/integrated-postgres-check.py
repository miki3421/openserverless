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

"""Run in the lab operator container after OPS has provisioned test users."""
import json
import subprocess
import pg8000.dbapi


def resource(kind, name):
    return json.loads(subprocess.check_output([
        "kubectl", "-n", "openserverless", "get", kind, name, "-o", "json"
    ]))


nodes = json.loads(subprocess.check_output(["kubectl", "get", "nodes", "-o", "json"]))["items"]
assert len(nodes) == 1 and nodes[0]["metadata"]["name"] == "ops-advanced-rc7"
host = resource("configmap", "config")["metadata"]["annotations"]["postgres_host"]
users = {name: resource("wsku", name)["spec"] for name in ["demopostgresuser", "testactionuser"]}


def connect(name, database=None, password=None):
    spec = users[name]
    return pg8000.dbapi.connect(host=host, port=5432, user=name,
        database=database or spec["postgres"]["database"],
        password=password if password is not None else spec["postgres"]["password"], timeout=10)


results = {}
for name in users:
    conn = connect(name)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT current_setting('server_version'), current_schema()")
        version, schema = cursor.fetchone()
        assert version.startswith("18."), version
        assert schema == f"{name}_schema", schema
        cursor.execute("SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user")
        assert tuple(cursor.fetchone()) == (False, False, False)
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
        vector_version = cursor.fetchone()[0]
        assert vector_version == "0.8.6"
        cursor.execute("DROP TABLE IF EXISTS advanced_records")
        cursor.execute("CREATE TABLE advanced_records (id integer PRIMARY KEY, payload jsonb, embedding vector(3))")
        cursor.execute("INSERT INTO advanced_records SELECT i, jsonb_build_object('id', i, 'owner', current_user), ARRAY[i::real/1000, (i%13)::real/13, (i%17)::real/17]::vector FROM generate_series(1,1000) i")
        cursor.execute("CREATE INDEX advanced_records_hnsw ON advanced_records USING hnsw (embedding vector_l2_ops)")
        conn.commit()
        cursor.execute("SELECT count(*), md5(string_agg(id::text || payload::text || embedding::text, ',' ORDER BY id)) FROM advanced_records")
        count, checksum = cursor.fetchone()
        assert count == 1000
        cursor.execute("SELECT count(*) FROM advanced_records WHERE payload->>'owner'=current_user")
        assert cursor.fetchone()[0] == 1000
        cursor.execute("SET enable_seqscan=off")
        cursor.execute("EXPLAIN SELECT id FROM advanced_records ORDER BY embedding <-> '[0.5,0.5,0.5]'::vector LIMIT 5")
        plan = "\n".join(row[0] for row in cursor.fetchall())
        assert "advanced_records_hnsw" in plan
        nearest_sql = "SELECT id FROM advanced_records ORDER BY embedding <-> '[0.5,0.5,0.5]'::vector LIMIT 5"
        cursor.execute(nearest_sql)
        approximate = [row[0] for row in cursor.fetchall()]
        cursor.execute("SET enable_indexscan=off")
        cursor.execute("SET enable_seqscan=on")
        cursor.execute(nearest_sql)
        exact = [row[0] for row in cursor.fetchall()]
        recall = len(set(approximate) & set(exact))/5
        assert len(approximate) == 5 and recall >= 0.8
        results[name] = dict(version=version, pgvector=vector_version, records=count, checksum=checksum,
            schema=schema, non_superuser=True, hnsw_index_used=True, nearest_ids=approximate,
            synthetic_recall_at5=recall)
    finally:
        conn.close()

for name, other in [("demopostgresuser", "testactionuser"), ("testactionuser", "demopostgresuser")]:
    try:
        conn = connect(name, users[other]["postgres"]["database"])
    except pg8000.dbapi.DatabaseError as error:
        assert error.args[0]["C"] == "42501", "unexpected isolation error"
        results[name]["other_database_denied"] = True
    else:
        conn.close()
        raise AssertionError(f"{name} could connect to another user's database")

try:
    conn = connect("demopostgresuser", password="intentionally-wrong-lab-password")
except pg8000.dbapi.DatabaseError as error:
    assert error.args[0]["C"] == "28P01", "unexpected authentication error"
    results["wrong_password_rejected"] = True
else:
    conn.close()
    raise AssertionError("invalid password accepted")

print(json.dumps(results, indent=2))
