import io
import os.path
import subprocess
import sys
import tempfile
import unittest

import diosgen


def parse_str(src: str):
    return diosgen.parse_lines(src.splitlines(), "-")

def generate_str(progdef: diosgen.ProgramDef):
    out = io.StringIO()
    diosgen.generate_main(progdef, out)
    return out.getvalue()

class TestParse(unittest.TestCase):

    def test_srcname(self):
        self.assertEqual(diosgen.parse_lines(["\tdios"], "unittest"), diosgen.ProgramDef(srcname="unittest"))

    def test_empty(self):
        self.assertEqual(parse_str("""\tdios
"""), diosgen.ProgramDef())

    def test_empty_bad(self):
        self.assertRaises(ValueError, lambda: parse_str(""))

    def test_comments_whitespace(self):
        self.assertEqual(parse_str(""";
; comment
;; comment ;
 ; comment

\tdios ; comment
\t
"""), diosgen.ProgramDef())

    def test_args(self):
        self.assertEqual(parse_str("""\tdios
\tirq irq_a, 0x4a, 42
\tirq irq_b, 0x4a, "str"
"""), diosgen.ProgramDef(irqs=[
    diosgen.IRQDef("irq_a", "0x4a", "42"),
    diosgen.IRQDef("irq_b", "0x4a", '"str"'),
]))

    def test_includes(self):
        self.assertEqual(parse_str("""\tdios
\tinclude "a.inc"
\tinclude\t"b.inc"
"""), diosgen.ProgramDef(includes=[
    "a.inc",
    "b.inc",
]))

    def test_modules(self):
        self.assertEqual(parse_str("""\tdios
\tmodule "a.inc"
\tmodule\t"b.inc"
"""), diosgen.ProgramDef(modules=[
    diosgen.ModuleDef("a.inc"),
    diosgen.ModuleDef("b.inc"),
]))

    def test_consts(self):
        self.assertEqual(parse_str("""\tdios
\tconst a, and
\tconst b, or
\tconst c, xor
\tconst d, add
\tconst e, sub
"""), diosgen.ProgramDef(consts=[
    diosgen.ConstDef("a", "&", -1),
    diosgen.ConstDef("b", "|", 0),
    diosgen.ConstDef("c", "^", 0),
    diosgen.ConstDef("d", "+", 0),
    diosgen.ConstDef("e", "-", 0),
]))

    def test_phases(self):
        self.assertEqual(parse_str("""\tdios
\tphase a
\tphase b
"""), diosgen.ProgramDef(phases=[
    diosgen.PhaseDef("a"),
    diosgen.PhaseDef("b"),
]))

    def test_irqs(self):
        self.assertEqual(parse_str("""\tdios
\tirq irq_a, f1, b1
\tirq irq_b, f2, b2
"""), diosgen.ProgramDef(irqs=[
    diosgen.IRQDef("irq_a", "f1", "b1"),
    diosgen.IRQDef("irq_b", "f2", "b2"),
]))

    def test_queues(self):
        self.assertEqual(parse_str("""\tdios
\tevqueue a
\tevqueue b
"""), diosgen.ProgramDef(queues=[
    diosgen.QueueDef("a"),
    diosgen.QueueDef("b"),
]))

    def test_queues(self):
        self.assertEqual(parse_str("""\tdios
\tevqueue a
\tevent b
\tevent c
"""), diosgen.ProgramDef(events=dict(
    b=diosgen.EventDef("b"),
    c=diosgen.EventDef("c"),
), queues=[
    diosgen.QueueDef("a", [
        diosgen.EventDef("b"),
        diosgen.EventDef("c"),
    ]),
]))

    def test_wakesrcs(self):
        self.assertEqual(parse_str("""\tdios
\twake f1, b1
\twake f2, b2
"""), diosgen.ProgramDef(wakesrcs=[
    diosgen.WakeSourceDef("f1", "b1"),
    diosgen.WakeSourceDef("f2", "b2"),
], sleepable=True))

    def test_wakealways(self):
        self.assertEqual(parse_str("""\tdios
\twake always
"""), diosgen.ProgramDef(sleepable=True))

    def test_wake_conflict(self):
        self.assertRaises(ValueError, lambda: parse_str("""\tdios
\twake f1, b1
\twake always
"""))
        self.assertRaises(ValueError, lambda: parse_str("""\tdios
\twake always
\twake f1, b1
"""))

class TestGenerate(unittest.TestCase):

    def assertGenerateValid(self, progdef: diosgen.ProgramDef, modules: dict[str, str]={}, asserts: str=""):
        progdef.includes.insert(0, "p16f887.inc")
        for name, src in modules.items():
            progdef.modules.append(diosgen.ModuleDef(name))

        mainsrc = generate_str(progdef).replace("\n\tend\n", "\n") + asserts + "\n\tend\n"

        with tempfile.TemporaryDirectory(prefix="diosgen_test") as tdir:
            with open(os.path.join(tdir, "unittest.asm"), "w") as f:
                f.write(mainsrc)

            for name, src in modules.items():
                with open(os.path.join(tdir, name), "w") as f:
                    print(src, file=f)

            try:
                subprocess.run(["gpasm", "--mpasm-compatible", "-p16f887", "-c", "unittest.asm"], text=True, check=True, cwd=tdir)
            except:
                print("Generated Source:\n" + mainsrc, file=sys.stderr)
                raise
            try:
                subprocess.run(["gplink", "--mplink-compatible", "-q", "-o", "final.hex", "unittest.o"], text=True, check=True, cwd=tdir)
            except:
                with open(os.path.join(tdir, "unittest.lst"), "r") as f:
                    lst = f.read()
                print("Object Listing:\n" + lst, file=sys.stderr)
                raise

    def test_empty(self):
        self.assertGenerateValid(diosgen.ProgramDef())

    def test_empty_module(self):
        self.assertGenerateValid(diosgen.ProgramDef(), modules={
            "a.inc": "",
        })

    def test_module_standard_phases(self):
        self.assertGenerateValid(diosgen.ProgramDef(), modules={
            "a.inc": """\tifdef diosh_udata
\tres 1
\tendif
\tifdef diosh_udata_shr
\tres 2
\tendif
\tifdef diosh_idata
\tdb 3
\tendif
\tifdef diosh_eedata
\tde 4
\tendif
\tifdef diosh_init
\tmovlw 5
\tendif
\tifdef diosph_init
\tmovlw 6
\tendif
\tifdef diosh_idle
\tmovlw 7
\tendif
\tifdef diosph_idle
\tmovlw 8
\tendif
\tifdef diosh_irq
\tmovlw 9
\tendif
\tifdef diosph_irq
\tmovlw 10
\tendif""",
            })

    def test_const(self):
        self.assertGenerateValid(diosgen.ProgramDef(
            consts=[diosgen.ConstDef("aconst", "|", 0)],
            sleepable=True), modules={
                "a.inc": "a_aconst\tequ\t1",
                "b.inc": "b_aconst\tequ\t42",
            }, asserts="""
\tif aconst != 43
\terror "aconst not merged correctly"
\tendif""")

    def test_custom_phase(self):
        self.assertGenerateValid(diosgen.ProgramDef(
            phases=[diosgen.PhaseDef("aphase")],
            sleepable=True), modules={
                "a.inc": """
\tifdef diosh_aphase
\tmovlw 1
TEST\tset 1
\tendif
\tifdef diosph_aphase
\tmovlw 2
TEST\tset TEST + 1
\tendif""",
            }, asserts="""
\tif TEST != 2
\terror "not all handlers instantiated"
\tendif""")

    def test_irq(self):
        self.assertGenerateValid(diosgen.ProgramDef(
            irqs=[diosgen.IRQDef("irq_inte", "INTCON", "INTE")],
            sleepable=True), modules={
                "a.inc": """\tifdef diosh_irq_inte
\tmovlw 1
TEST\tset 1
\tendif
\tifdef diosph_irq_inte
\tmovlw 2
TEST\tset TEST + 1
\tendif""",
            }, asserts="""
\tif TEST != 2
\terror "not all handlers instantiated"
\tendif
""")

    def test_queue_tiny(self):
        events = dict(
            A=diosgen.EventDef("A"),
            B=diosgen.EventDef("B"),
        )
        self.assertGenerateValid(diosgen.ProgramDef(
            events=events,
            queues=[diosgen.QueueDef("QUEUE", [events["A"], events["B"]], "idle")],
            sleepable=True), modules={
                "a.inc": """\tifdef diosh_idle
\tdiospost A
\tendif
\tifdef diosh_event_QUEUE_A
\tmovlw 1
TEST\tset 1
\tendif""",
            }, asserts="""
\tif TEST != 1
\terror "not all handlers instantiated"
\tendif
""")

    def test_queue_medium(self):
        events = dict(
            A=diosgen.EventDef("A"),
            B=diosgen.EventDef("B"),
            CC=diosgen.EventDef("CC"),
        )
        self.assertGenerateValid(diosgen.ProgramDef(
            events=events,
            queues=[diosgen.QueueDef("QUEUE", [events["A"], events["B"], events["CC"]], "idle")],
            sleepable=True), modules={
                "a.inc": """\tifdef diosh_idle
\tdiospost CC
\tendif
\tifdef diosh_event_QUEUE_CC
\tmovlw 1
TEST\tset 1
\tendif""",
            }, asserts="""
\tif TEST != 1
\terror "not all handlers instantiated"
\tendif
""")

    def test_queue_large(self):
        events = {f"E{i}": diosgen.EventDef(f"E{i}") for i in range(17)}
        self.assertGenerateValid(diosgen.ProgramDef(
            events=events,
            queues=[diosgen.QueueDef("QUEUE", list(events.values()), "idle")],
            sleepable=True), modules={
                "a.inc": """\tifdef diosh_idle
\tdiospost E16
\tendif
\tifdef diosh_event_QUEUE_E16
\tmovlw 1
TEST\tset 1
\tendif""",
            }, asserts="""
\tif TEST != 1
\terror "not all handlers instantiated"
\tendif
""")

    def test_sleepable(self):
        self.assertGenerateValid(diosgen.ProgramDef(
            sleepable=True), modules={
                "a.inc": """\tifdef diosh_sleep
\tmovlw 1
TEST\tset 1
\tendif
\tifdef diosph_sleep
\tmovlw 2
TEST\tset TEST + 1
\tendif""",
            }, asserts="""
\tif TEST != 2
\terror "not all handlers instantiated"
\tendif
""")

    def test_wakesrc(self):
        self.assertGenerateValid(diosgen.ProgramDef(
            wakesrcs=[diosgen.WakeSourceDef("INTCON", "INTE")],
            sleepable=True), modules={
                "a.inc": "",
            })


if __name__ == '__main__':
    unittest.main()
