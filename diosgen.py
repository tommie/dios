#! /usr/bin/python3
#
# DiOSGen generates assembly for Microchip PIC14/16 microcontrollers.
# It is a tiny RTOS for building modular source with events as the main
# communication method.
#
# Example:
#
#   diosgen -o mycode.dios.asm mycode.asm
#   gpasm   -p16f887 --mpasm-compatible -c mycode.dios.asm
#   gplink  --mplink-compatible mycode.dios.o

import argparse
import contextlib
from dataclasses import dataclass, field
import io
import os.path
import re
from typing import Iterator, TextIO, Union

LINE_RE = re.compile(r'(?P<lbl>\w+:?)?(?:\s+(?P<op>\w+)(?:\s+(?P<args>(?:[^;]|\\.|"(?:[^"\\]|\\.)*")+))?)?(?:\s*(?P<cmnt>;.*))?\s*$')

@dataclass
class ModuleDef:
    path: str

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.path))[0]

@dataclass
class ConstDef:
    name: str
    op: str
    init: str

@dataclass
class PhaseDef:
    name: str

@dataclass
class IRQDef:
    phase: str
    flagfile: str
    flagbit: str

@dataclass
class WakeSourceDef:
    enfile: str
    enbit: str

@dataclass
class EventDef:
    name: str

@dataclass
class QueueDef:
    name: str
    events: list[EventDef] = field(default_factory=list)
    phase: Union[str, None] = None

    @property
    def is_large(self): return len(self.events) > 16

    @property
    def is_tiny(self): return len(self.events) < 4

@dataclass
class ProgramDef:
    srcname: str = "-"
    includes: list[str] = field(default_factory=list)
    modules: list[ModuleDef] = field(default_factory=list)
    consts: list[ConstDef] = field(default_factory=list)
    phases: list[PhaseDef] = field(default_factory=list)
    irqs: list[IRQDef] = field(default_factory=list)
    events: dict[str, EventDef] = field(default_factory=dict)
    queues: list[QueueDef] = field(default_factory=list)
    wakesrcs: list[WakeSourceDef] = field(default_factory=list)
    sleepable: bool = False

    def phase_has_priorities(self, phase: str):
        return sum(1 for queuedef in self.queues if queuedef.phase == phase) > 1

STR_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
NUM_RE = re.compile(r'[0-9a-fA-FoOxX]+')
ID_RE = re.compile(r'\w+')

def splitargs(argstr: str):
    args = []

    while argstr:
        if argstr[0] == '"':
            m = STR_RE.match(argstr)
            if not m: raise ValueError(f"Unterminated string: {argstr}")
            args.append(m.group(0))
            argstr = argstr[len(m.group(0)):]
        elif argstr[0].isidentifier():
            m = ID_RE.match(argstr)
            args.append(m.group(0))
            argstr = argstr[len(m.group(0)):]
        elif argstr[0].isdigit():
            m = NUM_RE.match(argstr)
            args.append(m.group(0))
            argstr = argstr[len(m.group(0)):]
        else:
            raise ValueError(f"Unknown argument: {argstr}")

        argstr = argstr.lstrip()
        if not argstr: break
        if argstr[0] != ",":
            raise ValueError(f"Expected comma in argument: {argstr}")
        argstr = argstr[1:].lstrip()

    return args

def parse_lines(lines: Iterator[str], path: str):
    progdef = ProgramDef(path)
    dios = False
    wakealways = False

    lno = 0
    for line in lines:
        lno += 1
        if not line.strip():
            continue
        m = LINE_RE.match(line)
        if not m:
            raise ValueError(f"{path}:{lno} Invalid line: {line}")


        lbl = m.group("lbl")
        op = m.group("op")
        if not op:
            continue

        opargs = m.group("args")
        if opargs:
            try:
                opargs = splitargs(opargs)
            except ValueError as ex:
                raise ValueError(f"{path}:{lno} {ex}") from None
        cmnt = m.group("cmnt")
        if op == "include":
            if len(opargs) != 1:
                raise ValueError(f"{path}:{lno} Expected one argument to 'include': {opargs}")
            progdef.includes.append(opargs[0][1:-1])
        elif op == "module":
            if len(opargs) != 1:
                raise ValueError(f"{path}:{lno} Expected one argument to 'module': {opargs}")
            progdef.modules.append(ModuleDef(path=opargs[0][1:-1]))
        elif op == "evqueue":
            if len(opargs) != 1 and len(opargs) != 2:
                raise ValueError(f"{path}:{lno} Expected one or two arguments to 'evqueue': {opargs}")
            progdef.queues.append(QueueDef(opargs[0], phase=opargs[1] if len(opargs) > 1 else None))
        elif op == "event":
            if len(opargs) != 1:
                raise ValueError(f"{path}:{lno} Expected one argument to 'event': {opargs}")
            edef = progdef.events.setdefault(opargs[0], EventDef(opargs[0]))
            progdef.queues[-1].events.append(edef)
        elif op == "phase":
            if len(opargs) != 1:
                raise ValueError(f"{path}:{lno} Expected one argument to 'phase': {opargs}")
            progdef.phases.append(PhaseDef(opargs[0]))
        elif op == "irq":
            if len(opargs) != 3:
                raise ValueError(f"{path}:{lno} Expected three arguments to 'irq': {opargs}")
            if not opargs[0].startswith("irq_"):
                raise ValueError(f"{path}:{lno} Phase names used for IRQ must start with 'irq_': {opargs[0]}")
            progdef.irqs.append(IRQDef(opargs[0], opargs[1], opargs[2]))
        elif op == "wake":
            progdef.sleepable = True
            if len(opargs) == 1 and opargs[0] == "always":
                wakealways = True
            elif len(opargs) == 2:
                progdef.wakesrcs.append(WakeSourceDef(opargs[0], opargs[1]))
            else:
                raise ValueError(f"{path}:{lno} Expected two arguments to 'wake': {opargs}")
        elif op == "const":
            if len(opargs) != 2 :
                raise ValueError(f"{path}:{lno} Expected two arguments to 'const': {opargs}")
            cop, cinit = {
                "and": ("&", -1),
                "or": ("|", 0),
                "xor": ("^", 0),

                "add": ("+", 0),
                "sub": ("-", 0),
            }[opargs[1]]
            progdef.consts.append(ConstDef(opargs[0], cop, cinit))
        elif op == "dios":
            dios = True
        else:
            raise ValueError(f"{path}:{lno} Unknown events op: {line}")

    if not dios:
        raise ValueError(f"{path}:{lno} No 'dios' marker found in file")

    all_phases = set([None, "init", "idle", "irq", "sleep"] + [phasedef.name for phasedef in progdef.phases] + [irqdef.phase for irqdef in progdef.irqs])
    for queuedef in progdef.queues:
        if queuedef.phase not in all_phases:
            raise ValueError(f"Unknown phase requested for evqueue {queuedef.name}: {queuedef.phase}")

    # Using the same event at different priorities in the same phase makes no sense.
    for phase in all_phases:
        seen_events = {}
        for queuedef in progdef.queues:
            if not queuedef.phase or queuedef.phase != phase: continue
            for eventdef in queuedef.events:
                if eventdef.name in seen_events:
                    raise ValueError(f"Both queue {seen_events[eventdef.name].name} and {queuedef.name} in phase {phase!r} contain event {eventdef.name}")
                seen_events[eventdef.name] = queuedef

    if wakealways and progdef.wakesrcs:
        raise ValueError(f"{path}:{lno} Both 'wake always' and {len(progdef.wakesrcs)} explicit source(s) specified")

    return progdef

def generate_modules(aspect: str, progdef: ProgramDef, file: TextIO, main=True, post=True):
    if not progdef.modules: return

    if main:
        print(f"\t#define\tdiosh_{aspect}\t1", file=file)

        for moddef in progdef.modules:
            print(f'\tinclude\t"{moddef.path}"', file=file)

        print(f"\t#undefine\tdiosh_{aspect}", file=file)

    if post:
        print(f"\t#define\tdiosph_{aspect}\t1", file=file)
        for moddef in reversed(progdef.modules):
            print(f'\tinclude\t"{moddef.path}"', file=file)

        print(f"\t#undefine\tdiosph_{aspect}", file=file)

def generate_consts(progdef: ProgramDef, file: TextIO):
    if progdef.events:
        print("\tcblock\t0\t; Events", file=file)
        print(f"\t\t{', '.join(eventdef.name for eventdef in progdef.events.values())}", file=file)
        print("\tendc", file=file)

    if progdef.queues:
        if progdef.events: print(file=file)
        print("\tcblock\t0\t; Queues", file=file)
        print(f"\t\t{', '.join(queuedef.name for queuedef in progdef.queues)}", file=file)
        print("\tendc", file=file)

def generate_queue_consts(queuedef: QueueDef, qid: int, file: TextIO):
    print(f"\tcblock\t{qid} << 8\t; Queue event bits", file=file)
    print(f"\t\t{', '.join(queuedef.name + '_' + eventdef.name for eventdef in queuedef.events)}", file=file)
    print("\tendc", file=file)

def generate_queue_udata(queuedef: QueueDef, file: TextIO):
    # diosq_state bits
    #
    #   0  for large queues; whether any event is posted.
    #   1  for prioritized queues in phases; whether any event was processed.
    print(f"""dios_qsz_{queuedef.name}\tequ\t{len(queuedef.events)}
dios_qstate_{queuedef.name}\tres\t1
dios_q_{queuedef.name}\tres\t(dios_qsz_{queuedef.name} + 7) / 8""", file=file)

def generate_queue_macros(queuedef: QueueDef, file: TextIO):
    print(f"""diospost_{queuedef.name.lower()}\tmacro\tbit
\tbanksel\tdios_q_{queuedef.name} + ((bit) + 7) / 8
\tbsf\tdios_q_{queuedef.name} + ((bit) + 7) / 8, (bit) % 8""", file=file)
    if queuedef.is_large:
        # This is interrupt safe: if the event flag is handled before
        # we set state, there is nothing more to do, and setting state
        # will just waste cycles.
        print(f"""\tbanksel\tdios_qstate_{queuedef.name}
\tbsf\tdios_qstate_{queuedef.name}, 0""", file=file)
    print("\tendm", file=file)

    # Skip if queue has no event posted.
    print(f"diosqsc_{queuedef.name.lower()}\tmacro", file=file)
    if queuedef.is_large:
        print(f"""\tbanksel\tdios_qstate_{queuedef.name}
\tbtfsc\tdios_qstate_{queuedef.name}, 0""", file=file)
    else:
        if len(queuedef.events) <= 8:
            print(f"""\tbanksel\tdios_q_{queuedef.name}
\tmovf\tdios_q_{queuedef.name}, F""", file=file)
        else:
            print("\tclrw", file=file)
            for i in range((len(queuedef.events) + 7) // 8):
                print(f"""\tbanksel\tdios_q_{queuedef.name} + {i}
\tiorwf\tdios_q_{queuedef.name} + {i}, W""", file=file)
        print(f"\tbtfsc\tSTATUS, Z", file=file)
    print("\tendm", file=file)

    if not queuedef.phase:
        print(file=file)
        print(f"""process_{queuedef.name.lower()}\tmacro
\tpagesel\thandle_{queuedef.name.lower()}
\tcall\thandle_{queuedef.name.lower()}
\tendm""", file=file)

def generate_queue_init(queuedef: QueueDef, file: TextIO):
    print(f"""\tbanksel\tdios_qstate_{queuedef.name}
\tclrf\tdios_qstate_{queuedef.name}""", file=file)
    for i in range((len(queuedef.events) + 7) // 8):
        print(f"""\tbanksel\tdios_q_{queuedef.name} + {i}
\tclrf\tdios_q_{queuedef.name} + {i}""", file=file)

def generate_queue_handler(queuedef: QueueDef, progdef: ProgramDef, startlabel: str, file: TextIO, implfile: TextIO):
    has_prios = progdef.phase_has_priorities(queuedef.phase)

    print(f"\t; Queue handler for {queuedef.name}", file=file)

    qendlabel = f"dios_qend_{queuedef.name}"
    if queuedef.is_large:
        print(f"""\tbcf\tdios_qstate_{queuedef.name}, 1
\tpagesel\t{qendlabel}
\tbanksel\tdios_qstate_{queuedef.name}
\tbtfss\tdios_qstate_{queuedef.name}, 0
\tgoto\t{qendlabel}
\tbcf\tdios_qstate_{queuedef.name}, 0""", file=file)
        if has_prios:
            print(f"""\tbanksel\tdios_qstate_{queuedef.name} + {i}
\tbsf\tdios_qstate_{queuedef.name}, 1""", file=file)
    elif has_prios:
        print(f"""\tbcf\tdios_qstate_{queuedef.name}, 1""", file=file)

    for i in range((len(queuedef.events) + 7) // 8):
        wendlabel = f"dios_w{i}end_{queuedef.name}"
        if not queuedef.is_tiny:
            print(f"""\tpagesel\t{wendlabel}
\tbanksel\tdios_q_{queuedef.name} + {i}
\tmovf\tdios_q_{queuedef.name} + {i}, F
\tbtfsc\tSTATUS, Z
\tgoto\t{wendlabel}""", file=file)
            if has_prios:
                print(f"""\tbanksel\tdios_qstate_{queuedef.name} + {i}
\tbsf\tdios_qstate_{queuedef.name}, 1""", file=file)

        endbit = min(len(queuedef.events), i * 8 + 8)
        for j in range(i * 8, endbit):
            bimpllabel = f"dios_b{j}impl_{queuedef.name}"
            bendlabel = f"dios_b{j}end_{queuedef.name}"
            print(f"""\tpagesel\t{bimpllabel}
\tbtfsc\tdios_q_{queuedef.name} + {i}, {j - i * 8}
\tgoto\t{bimpllabel}""", file=file)

            # The out-of-line implementation.
            print(f"""{bimpllabel}:
\tbcf\tdios_q_{queuedef.name} + {i}, {j - i * 8}""", file=implfile)
            generate_modules(f"event_{queuedef.name}_{queuedef.events[j].name}", progdef, implfile)
            if queuedef.is_tiny and has_prios:
                print(f"""\tbanksel\tdios_qstate_{queuedef.name} + {i}
\tbsf\tdios_qstate_{queuedef.name}, 1""", file=implfile)
            if j != endbit - 1:
                print(f"""\tbanksel\tdios_q_{queuedef.name} + {i}""", file=implfile)
            print(f"""\tpagesel\t{bendlabel}
\tgoto\t{bendlabel}""", file=implfile)

            print(f"""{bendlabel}:""", file=file)

        if not queuedef.is_tiny:
            if not queuedef.is_large and has_prios:
                print(f"""\tbsf\tdios_qstate_{queuedef.name}, 1""", file=file)
            print(f"{wendlabel}:", file=file)

    if has_prios:
        if not queuedef.is_large:
            print(f"""\tpagesel\t{startlabel}
\tbanksel\tdios_qstate_{queuedef.name}
\tbtfsc\tdios_qstate_{queuedef.name}, 1
\tgoto\t{startlabel}""", file=file)
        else:
            print(f"""\tpagesel\t{startlabel}
\tgoto\t{startlabel}""", file=file)

    if queuedef.is_large:
        print(f"{qendlabel}:", file=file)

def generate_constdef(constdef: ConstDef, progdef: ProgramDef, file: TextIO):
    print(f"{constdef.name}\tset\t{constdef.init}", file=file)
    for moduledef in progdef.modules:
        modname = moduledef.name
        print(f"""\tifdef\t{modname}_{constdef.name}
{constdef.name}\tset\t{constdef.name} {constdef.op} ({modname}_{constdef.name})
\tendif""", file=file)

@contextlib.contextmanager
def phase_code(phasedef: PhaseDef, progdef: ProgramDef, file: TextIO, himplfile: TextIO):
    startlabel = "phase_" + phasedef.name
    print(startlabel + ":", file=file)

    generate_modules(phasedef.name, progdef, file, post=False)

    yield phasedef

    for queuedef in progdef.queues:
        if queuedef.phase != phasedef.name:
            continue
        print(file=file)
        generate_queue_handler(queuedef, progdef, startlabel, file, himplfile)

    generate_modules(phasedef.name, progdef, file, main=False)

def generate_phase(phasedef: PhaseDef, progdef: ProgramDef, file: TextIO, himplfile: TextIO):
    with phase_code(phasedef, progdef, file, himplfile):
        pass

def generate_sleep(progdef: ProgramDef, file: TextIO, himplfile: TextIO):
    # Set C to whether there are any wake-up soruces enabled.
    #
    # NOTE: This assumes group bits like PEIE are always enabled.
    if progdef.wakesrcs:
        # Check that there are wake-up sources enabled.
        print("\tbcf\tSTATUS, C", file=file)
    else:
        # Assume there are wake-up sources.
        print("\tbsf\tSTATUS, C", file=file)

    for wakesrcdef in progdef.wakesrcs:
        print(f"""\tbanksel\t{wakesrcdef.enfile}
\tbtfsc\t{wakesrcdef.enfile}, {wakesrcdef.enbit}
\tbsf\tSTATUS, C""", file=file)

    # Inhibit sleep if interrupts are disabled.
    print("""\tbanksel\tINTCON
\tbtfss\tINTCON, GIE
\tbcf\tSTATUS, C""", file=file)

    print(file=file)
    for queuedef in progdef.queues:
        if queuedef.phase != "idle":
            continue
        print(f"""\tdiosqsc_{queuedef.name.lower()}
\tbcf\tSTATUS, C""", file=file)

    print("""
\tpagesel\tphase_sleep_done
\tbtfss\tSTATUS, C
\tgoto\tphase_sleep_done""", file=file)

    with phase_code(PhaseDef("sleep"), progdef, file, himplfile):
        print("\tsleep", file=file)

    print("phase_sleep_done:", file=file)

def generate_main(progdef: ProgramDef, file: TextIO):
    print(f"\t; Generated by diosgen from {progdef.srcname!r}. Do not modify directly.", file=file)

    if progdef.includes:
        print(file=file)
        for path in progdef.includes:
            print(f'\tinclude\t"{path}"', file=file)

    # Data definitions.
    print("""
\tudata""", file=file)
    generate_consts(progdef, file)
    for qid, queuedef in enumerate(progdef.queues):
        print(file=file)
        generate_queue_udata(queuedef, file)
        generate_queue_consts(queuedef, qid, file)

    # Gathered constants.
    for constdef in progdef.consts:
        print(file=file)
        generate_constdef(constdef, progdef, file)

    if progdef.modules:
        print(file=file)
        generate_modules("udata", progdef, file, post=False)

    print(file=file)
    print("""\tudata_shr
dios_irqsave_w\tres\t1
dios_irqsave_status\tres\t1
dios_irqsave_pclath\tres\t1""", file=file)
    generate_modules("udata_shr", progdef, file, post=False)

    if progdef.modules:
        print(file=file)
        print("\tidata", file=file)
        generate_modules("idata", progdef, file, post=False)

    # Queue macros.
    for queuedef in progdef.queues:
        print(file=file)
        generate_queue_macros(queuedef, file)

    if progdef.events:
        print("""
diospost\tmacro\tevent""", file=file)
        for eventdef in progdef.events.values():
            print(f"\tif\tevent == {eventdef.name}", file=file)
            for queuedef in progdef.queues:
                if eventdef not in queuedef.events: continue
                print(f"\tdiospost_{queuedef.name.lower()}\t{queuedef.name}_{eventdef.name}", file=file)
            print("\tendif", file=file)
        print("\tendm", file=file)

    print("""
\tcode""", file=file)

    if progdef.modules:
        print("""
\torg\t0x2100""", file=file)
        generate_modules("eedata", progdef, file, post=False)

    # Reset.
    print("""
\torg\t0
\tpagesel\t_start
\tgoto\t_start""", file=file)

    # Interrupt phase.
    print("""
\torg\t4
_irq:
\tmovwf\tdios_irqsave_w
\tswapf\tSTATUS, W
\tmovwf\tdios_irqsave_status
\tmovf\tPCLATH, W
\tmovwf\tdios_irqsave_pclath
""", file=file)

    irqhimplfile = io.StringIO()
    with phase_code(PhaseDef(name="irq"), progdef, file, irqhimplfile):
        for irqdef in progdef.irqs:
            impllabel = "dios_irqimpl_" + irqdef.phase
            print(f"""\tpagesel\t{impllabel}
\tbanksel\t{irqdef.flagfile}
\tbtfsc\t{irqdef.flagfile}, {irqdef.flagbit}
\tgoto\t{impllabel}""", file=file)

            # The out-of-line interrupt handler, which in turn may
            # have twice-out-of-line event handlers.
            print(f"""{impllabel}:
\tbcf\t{irqdef.flagfile}, {irqdef.flagbit}""", file=irqhimplfile)
            irqqueuehimplfile = io.StringIO()
            generate_phase(PhaseDef(name=irqdef.phase), progdef, irqhimplfile, irqqueuehimplfile)
            print(f"""\tpagesel\tdios_irqend_{irqdef.phase}
\tgoto\tdios_irqend_{irqdef.phase}""", file=irqqueuehimplfile)

            # We want the event handlers as close as possible to the
            # interrupt handler.
            if irqqueuehimplfile.getvalue():
                print(file=file)
                irqhimplfile.write(irqqueuehimplfile.getvalue())

            print(f"""dios_irqend_{irqdef.phase}:""", file=file)

    print("""
\tmovf\tdios_irqsave_pclath, W
\tmovwf\tPCLATH
\tswapf\tdios_irqsave_status, W
\tmovwf\tSTATUS
\tswapf\tdios_irqsave_w, F
\tswapf\tdios_irqsave_w, W
\tretfie""", file=file)

    if irqhimplfile.getvalue():
        print(file=file)
        file.write(irqhimplfile.getvalue())

    # Entry.
    print("""
_start:""", file=file)
    for queuedef in progdef.queues:
        print(file=file)
        generate_queue_init(queuedef, file)

    # Initialization.
    print(file=file)
    mainhimplfile = io.StringIO()
    generate_phase(PhaseDef(name="init"), progdef, file, mainhimplfile)

    # The main loop, with idle phase.
    print(file=file)
    generate_phase(PhaseDef(name="idle"), progdef, file, mainhimplfile)

    if progdef.sleepable:
        print(file=file)
        generate_sleep(progdef, file, mainhimplfile)

    print("""
\tpagesel\tphase_idle
\tgoto\tphase_idle""", file=file)

    if mainhimplfile.getvalue():
        print(file=file)
        file.write(mainhimplfile.getvalue())

    if progdef.modules:
        print(file=file)
        generate_modules("code", progdef, file, post=False)

    # Custom phases
    for phasedef in progdef.phases:
        print(file=file)
        phasehimplfile = io.StringIO()
        generate_phase(phasedef, progdef, file, phasehimplfile)
        print("""\treturn""", file=file)

        if phasehimplfile.getvalue():
            print(file=file)
            file.write(phasehimplfile.getvalue())

    # Queues not assigned to built-in phases.
    for queuedef in progdef.queues:
        if queuedef.phase:
            continue
        print(file=file)
        startlabel = "handle_" + queuedef.name.lower()
        print(startlabel + ":", file=file)
        queuehimplfile = io.StringIO()
        generate_queue_handler(queuedef, progdef, startlabel, file, queuehimplfile)
        print(f"\treturn", file=file)

        if queuehimplfile.getvalue():
            print(file=file)
            file.write(queuehimplfile.getvalue())

    print("""
\tend""", file=file)

def main():
    argp = argparse.ArgumentParser()
    argp.add_argument("--output", "-o", default="-", type=argparse.FileType("w"), help="output asm file")
    argp.add_argument("input", type=argparse.FileType("r"), help="input asm file")
    args = argp.parse_args()

    progdef = parse_lines(args.input, args.input.name)
    generate_main(progdef, args.output)

if __name__ == "__main__":
    main()
