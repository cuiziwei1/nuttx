############################################################################
# tools/gdb/__init__.py
#
# SPDX-License-Identifier: Apache-2.0
#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.  The
# ASF licenses this file to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance with the
# License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations
# under the License.
#
############################################################################

import glob
import os
import sys

import gdb

python_dir = os.path.abspath(__file__)
python_dir = os.path.dirname(python_dir)

sys.path.insert(1, python_dir)
# Search the python dir for all .py files, and source each
py_files = glob.glob(f"{python_dir}/*.py")
py_files.remove(os.path.abspath(__file__))

gdb.execute("set pagination off")
gdb.write("set pagination off\n")
gdb.execute("set python print-stack full")
gdb.write("set python print-stack full\n")
for py_file in py_files:
    gdb.execute(f"source {py_file}")
    gdb.write(f"source {py_file}\n")

gdb.execute('handle SIGUSR1 "nostop" "pass" "noprint"')
gdb.write('"handle SIGUSR1 "nostop" "pass" "noprint"\n')
