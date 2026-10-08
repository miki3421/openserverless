-- Licensed to the Apache Software Foundation (ASF) under one
-- or more contributor license agreements. See the NOTICE file
-- distributed with this work for additional information
-- regarding copyright ownership. The ASF licenses this file
-- to you under the Apache License, Version 2.0 (the
-- "License"); you may not use this file except in compliance
-- with the License. You may obtain a copy of the License at
--
--   http://www.apache.org/licenses/LICENSE-2.0
--
-- Unless required by applicable law or agreed to in writing,
-- software distributed under the License is distributed on an
-- "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
-- KIND, either express or implied. See the License for the
-- specific language governing permissions and limitations
-- under the License.

\set ON_ERROR_STOP on
SELECT version();
SELECT extname, extversion FROM pg_extension ORDER BY extname;
CREATE SCHEMA advanced_vector_lab;
CREATE TABLE advanced_vector_lab.synthetic (id integer PRIMARY KEY, embedding vector(3));
INSERT INTO advanced_vector_lab.synthetic VALUES (1, '[1,0,0]'), (2, '[0,1,0]'), (3, '[0,0,1]');
CREATE INDEX synthetic_hnsw ON advanced_vector_lab.synthetic USING hnsw (embedding vector_l2_ops);
SELECT id, embedding <-> '[1,0,0]'::vector AS distance FROM advanced_vector_lab.synthetic ORDER BY distance, id;
SELECT database_name, collection_name FROM documentdb_api_catalog.collections ORDER BY database_name, collection_name;
