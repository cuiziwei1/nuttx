############################################################################
# tools/gdb/utils.py
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

import re

import gdb
from macros import fetch_macro_info, try_expand


class CachedType:
    """Cache a type object, so that we can reconnect to the new_objfile event"""

    def __init__(self, name):
        self._type = None
        self._name = name

    def _new_objfile_handler(self, event):
        self._type = None
        gdb.events.new_objfile.disconnect(self._new_objfile_handler)

    def get_type(self):
        if self._type is None:
            self._type = gdb.lookup_type(self._name)
            if self._type is None:
                raise gdb.GdbError("cannot resolve type '{0}'".format(self._name))
            if hasattr(gdb, "events") and hasattr(gdb.events, "new_objfile"):
                gdb.events.new_objfile.connect(self._new_objfile_handler)
        return self._type


long_type = CachedType("long")


class MacroCtx:
    """
    This is a singleton class wich only initializes once to
    cache a context of macro definition which can be queried later
    TODO: we only deal with single ELF at the moment for simplicity
    If you load more object files while debugging, only the first one gets loaded
    will be used to retrieve macro information
    """

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "instance"):
            cls.instance = super(MacroCtx, cls).__new__(cls)
        return cls.instance

    def __init__(self, filename):
        self._macro_map = {}
        self._file = filename

        self._macro_map = fetch_macro_info(filename)

    @property
    def macro_map(self):
        return self._macro_map

    @property
    def objfile(self):
        return self._file


if len(gdb.objfiles()) > 0:
    macroctx = MacroCtx(gdb.objfiles()[0].filename)
else:
    raise gdb.GdbError("An executable file must be provided")


# Common Helper Functions


def get_long_type():
    """Return the cached long type object"""
    global long_type
    return long_type.get_type()


def offset_of(typeobj, field):
    """Return the offset of a field in a structure"""
    element = gdb.Value(0).cast(typeobj)
    return int(str(element[field].address).split()[0], 16)


def container_of(ptr, typeobj, member):
    """Return pointer to containing data structure"""
    return (ptr.cast(get_long_type()) - offset_of(typeobj, member)).cast(typeobj)


class ContainerOf(gdb.Function):
    """Return pointer to containing data structure.

    $container_of(PTR, "TYPE", "ELEMENT"): Given PTR, return a pointer to the
    data structure of the type TYPE in which PTR is the address of ELEMENT.
    Note that TYPE and ELEMENT have to be quoted as strings."""

    def __init__(self):
        super(ContainerOf, self).__init__("container_of")

    def invoke(self, ptr, typename, elementname):
        return container_of(
            ptr, gdb.lookup_type(typename.string()).pointer(), elementname.string()
        )


ContainerOf()


def gdb_eval_or_none(expresssion):
    """Evaluate an expression and return None if it fails"""
    try:
        return gdb.parse_and_eval(expresssion)
    except gdb.error:
        return None


def get_symbol_value(name):
    """Return the value of a symbol value etc: Variable, Marco"""

    expr = None

    try:
        gdb.execute("set $_%s = %s" % (name, name))
        expr = "$_%s" % (name)
    except gdb.error:
        expr = try_expand(name, macroctx.macro_map)
    return gdb_eval_or_none(expr)


def hexdump(address, size):
    inf = gdb.inferiors()[0]
    mem = inf.read_memory(address, size)
    bytes = mem.tobytes()
    for i in range(0, len(bytes), 16):
        chunk = bytes[i : i + 16]
        gdb.write(f"{i + address:08x}  ")
        hex_values = " ".join(f"{byte:02x}" for byte in chunk)
        hex_display = f"{hex_values:<47}"
        gdb.write(hex_display)
        ascii_values = "".join(
            chr(byte) if 32 <= byte <= 126 else "." for byte in chunk
        )
        gdb.write(f"  {ascii_values} \n")


def is_decimal(s):
    return re.fullmatch(r"\d+", s) is not None


def is_hexadecimal(s):
    return re.fullmatch(r"0[xX][0-9a-fA-F]+|[0-9a-fA-F]+", s) is not None


class Hexdump(gdb.Command):
    """hexdump address/symbol <size>"""

    def __init__(self):
        super(Hexdump, self).__init__("hexdump", gdb.COMMAND_USER)

    def invoke(self, args, from_tty):
        argv = args.split(" ")
        address = 0
        size = 0
        if argv[0] == "":
            gdb.write("Usage: hexdump address/symbol <size>\n")
            return

        if is_decimal(argv[0]) or is_hexadecimal(argv[0]):
            address = int(argv[0], 0)
            size = int(argv[1], 0)
        else:
            var = gdb.parse_and_eval(f"{argv[0]}")
            address = int(var.address)
            size = int(var.type.sizeof)
            gdb.write(f"{argv[0]} {hex(address)} {int(size)}\n")

        hexdump(address, size)


Hexdump()


# Machine Specific Helper Functions


BIG_ENDIAN = 0
LITTLE_ENDIAN = 1
target_endianness = None


def get_target_endianness():
    """Return the endianness of the target"""
    global target_endianness
    if target_endianness is None:
        endian = gdb.execute("show endian", to_string=True)
        if "little endian" in endian:
            target_endianness = LITTLE_ENDIAN
        elif "big endian" in endian:
            target_endianness = BIG_ENDIAN
        else:
            raise gdb.GdbError("unknown endianness '{0}'".format(str(endian)))
    return target_endianness


def read_memoryview(inf, start, length):
    """Read memory from the target and return a memoryview object"""
    m = inf.read_memory(start, length)
    if type(m) is memoryview:
        return m
    return memoryview(m)


def read_u16(buffer, offset):
    """Read a 16-bit unsigned integer from a buffer"""
    buffer_val = buffer[offset : offset + 2]
    value = [0, 0]

    if type(buffer_val[0]) is str:
        value[0] = ord(buffer_val[0])
        value[1] = ord(buffer_val[1])
    else:
        value[0] = buffer_val[0]
        value[1] = buffer_val[1]

    if get_target_endianness() == LITTLE_ENDIAN:
        return value[0] + (value[1] << 8)
    else:
        return value[1] + (value[0] << 8)


def read_u32(buffer, offset):
    """Read a 32-bit unsigned integer from a buffer"""
    if get_target_endianness() == LITTLE_ENDIAN:
        return read_u16(buffer, offset) + (read_u16(buffer, offset + 2) << 16)
    else:
        return read_u16(buffer, offset + 2) + (read_u16(buffer, offset) << 16)


def read_u64(buffer, offset):
    """Read a 64-bit unsigned integer from a buffer"""
    if get_target_endianness() == LITTLE_ENDIAN:
        return read_u32(buffer, offset) + (read_u32(buffer, offset + 4) << 32)
    else:
        return read_u32(buffer, offset + 4) + (read_u32(buffer, offset) << 32)


def read_ulong(buffer, offset):
    """Read a long from a buffer"""
    if get_long_type().sizeof == 8:
        return read_u64(buffer, offset)
    else:
        return read_u32(buffer, offset)


target_arch = None


def is_target_arch(arch, exact=False):
    """
    For non exactly match, this function will
    return True if the target architecture contains
    keywords of an ARCH family. For example, x86 is
    contained in i386:x86_64.
    For exact match, this function will return True if
    the target architecture is exactly the same as ARCH.
    """
    if hasattr(gdb.Frame, "architecture"):
        archname = gdb.newest_frame().architecture().name()

        return arch in archname if not exact else arch == archname
    else:
        global target_arch
        if target_arch is None:
            target_arch = gdb.execute("show architecture", to_string=True)
            pattern = r'set to "(.*?)"\s*(\(currently (".*")\))?'
            match = re.search(pattern, target_arch)

            candidate = match.group(1)

            if candidate == "auto":
                target_arch = match.group(3)
            else:
                target_arch = candidate

        return arch in target_arch if not exact else arch == target_arch


# Kernel Specific Helper Functions


def is_target_smp():
    """Return Ture if the target use smp"""

    if gdb.lookup_global_symbol("g_assignedtasks"):
        return True
    else:
        return False


# FIXME: support RISC-V/X86/ARM64 etc.
def in_interrupt_context(cpuid=0):
    frame = gdb.selected_frame()

    if is_target_arch("arm"):
        xpsr = int(frame.read_register("xpsr"))
        return xpsr & 0xF
    else:
        # TODO: figure out a more proper way to detect if
        # we are in an interrupt context
        g_current_regs = gdb_eval_or_none("g_current_regs")
        return not g_current_regs[cpuid]


def get_arch_sp_name():
    if is_target_arch("arm", exact=True):
        return "sp"
    elif is_target_arch("i386", exact=True):
        return "esp"
    elif is_target_arch("i386:x86-64", exact=True):
        return "rsp"
    else:
        raise gdb.GdbError("Not implemented yet")


def get_arch_pc_name():
    if is_target_arch("arm", exact=True):
        return "pc"
    elif is_target_arch("i386", exact=True):
        return "eip"
    elif is_target_arch("i386:x86-64", exact=True):
        return "rip"
    else:
        raise gdb.GdbError("Not implemented yet")


def get_register_byname(regname, tcb=None):
    frame = gdb.selected_frame()

    # If no tcb is given then we can directly used the register from
    # the cached frame by GDB
    if not tcb:
        return int(frame.read_register(regname))

    # Ok, let's take it from the context in the given tcb
    arch = frame.architecture()
    tcbinfo = gdb.parse_and_eval("g_tcbinfo")

    i = 0
    for reg in arch.registers():
        if reg.name == regname:
            break
        i += 1

    regs = tcb["xcp"]["regs"].cast(gdb.lookup_type("char").pointer())
    value = gdb.Value(regs + tcbinfo["reg_off"]["p"][i]).cast(
        gdb.lookup_type("uintptr_t").pointer()
    )[0]

    return int(value)


def get_tcbs():
    # In case we have created/deleted tasks at runtime, the tcbs will change
    # so keep it as fresh as possible
    pidhash = gdb.parse_and_eval("g_pidhash")
    npidhash = gdb.parse_and_eval("g_npidhash")

    return [pidhash[i] for i in range(0, npidhash) if pidhash[i]]
