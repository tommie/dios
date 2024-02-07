import os.path
import shutil
import subprocess
import sys
import tempfile
import unittest

import diosgen

PRESERVE_BUILD = False

class TestWDT(unittest.TestCase):

    def assertGenerateValid(self, progdef: diosgen.ProgramDef):
        progdef.includes.insert(0, "p16f887.inc")
        stem = os.path.splitext(progdef.srcname)[0]

        with tempfile.TemporaryDirectory(prefix="dios_wdt_test") as tdir:
            with open(os.path.join(tdir, progdef.srcname), "w") as f:
                diosgen.generate_main(progdef, f)

            for moduledef in progdef.modules:
                shutil.copyfile(moduledef.path, os.path.join(tdir, moduledef.path))

            try:
                subprocess.run(["gpasm", "--mpasm-compatible", "-p16f887", "-r", "dec", "-c", progdef.srcname], text=True, check=True, cwd=tdir)
            except:
                with open(os.path.join(tdir, progdef.srcname), "r") as f:
                    mainsrc = f.read()
                print("Generated Source:\n" + mainsrc, file=sys.stderr)
                raise

            try:
                subprocess.run(["gplink", "--mplink-compatible", "-q", "-o", stem + ".hex", stem + ".o"], text=True, check=True, cwd=tdir)
            except:
                with open(os.path.join(tdir, stem + ".lst"), "r") as f:
                    lst = f.read()
                print("Object Listing:\n" + lst, file=sys.stderr)
                raise

            if PRESERVE_BUILD:
                shutil.copyfile(os.path.join(tdir, stem + ".cod"), stem + ".cod")
                shutil.copyfile(os.path.join(tdir, stem + ".hex"), stem + ".hex")

    def test_empty(self):
        with open("wdt_test.asm", "r") as f:
            progdef = diosgen.parse_lines(f, "wdt_test.asm")

        self.assertGenerateValid(progdef)


if __name__ == '__main__':
    unittest.main()
