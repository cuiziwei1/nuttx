/****************************************************************************
 * libs/libc/spawn/lib_psa_setflags.c
 *
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed to the Apache Software Foundation (ASF) under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.  The
 * ASF licenses this file to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance with the
 * License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations
 * under the License.
 *
 ****************************************************************************/

/****************************************************************************
 * Included Files
 ****************************************************************************/

#include <nuttx/config.h>

#include <spawn.h>
#include <assert.h>

/****************************************************************************
 * Public Functions
 ****************************************************************************/

/****************************************************************************
 * Name: posix_spawnattr_setflags
 *
 * Description:
 *   The posix_spawnattr_setflags() function will set the spawn-flags
 *   attribute in an initialized attributes object referenced by attr.
 *
 * Input Parameters:
 *   attr - The address spawn attributes to be used.
 *   flags - The new value of the spawn flags
 *
 * Returned Value:
 *   On success, these functions return 0; on failure they return an error
 *   number from <errno.h>.
 *
 ****************************************************************************/

int posix_spawnattr_setflags(FAR posix_spawnattr_t *attr, short flags)
{
  DEBUGASSERT(attr && (flags & ~0xff) == 0);
  attr->flags = (uint8_t)flags;
  return OK;
}
