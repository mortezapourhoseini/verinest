"""Backend unit tests (no simulator needed): python3 -m unittest discover tests"""
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verinest import explain, formatter, tbgen, vparse  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestParser(unittest.TestCase):
    def test_examples_have_one_testbench_top(self):
        for d in sorted(glob.glob(os.path.join(ROOT, 'examples', '*/'))):
            files = {os.path.basename(f): open(f).read() for f in glob.glob(d + '*.v')}
            mods = vparse.parse_project(files)
            tops = [m['name'] for m in mods if m['is_top']]
            self.assertEqual(len(tops), 1, (d, tops))
            self.assertTrue(tops[0].startswith('tb_'), d)

    def test_ansi_ports_and_params(self):
        m = vparse.parse_file('module a #(parameter W = 8) (input wire [W-1:0] x, output reg y);\nendmodule')[0]
        self.assertEqual([p['name'] for p in m['ports']], ['x', 'y'])
        self.assertEqual(m['ports'][0]['width'], 8)
        self.assertEqual(m['params'][0]['name'], 'W')

    def test_non_ansi_ports(self):
        m = vparse.parse_file('module a (x, y);\n input [3:0] x;\n output y;\n reg y;\nendmodule')[0]
        self.assertEqual([(p['name'], p['dir'], p['width']) for p in m['ports']],
                         [('x', 'input', 4), ('y', 'output', 1)])


class TestFormatter(unittest.TestCase):
    def test_examples_are_already_clean_and_idempotent(self):
        for f in glob.glob(os.path.join(ROOT, 'examples', '*', '*.v')):
            text = open(f).read()
            once = formatter.format_verilog(text)
            self.assertEqual(once, formatter.format_verilog(once), f)
            self.assertEqual(once, text, f)

    def test_only_whitespace_changes(self):
        src = "module m(input a,output reg y);\nalways@(*)begin\nif(a)\ny=1;\nelse y=0;\nend\nendmodule\n"
        out = formatter.format_verilog(src)
        self.assertEqual(''.join(src.split()), ''.join(out.split()))
        self.assertIn('    always @(*) begin', out)


class TestExplain(unittest.TestCase):
    def test_missing_semicolon_hint(self):
        files = {'a.v': 'module a;\n  wire t\n  assign t = 1;\nendmodule\n'}
        d = explain.parse_iverilog('/x/a.v:3: syntax error\n', {'/x/a.v': 'a.v'})
        d = explain.enrich(d, files)
        self.assertEqual(d[0]['related_line'], 2)

    def test_unclosed_begin(self):
        d = explain.structure_check('module m;\ninitial begin\nendmodule\n', 'm.v')
        self.assertEqual(d[0]['line'], 2)

    def test_verilator_latch(self):
        d = explain.parse_verilator("%Warning-LATCH: /x/a.v:4:3: Latch inferred for signal 'y'", {'/x/a.v': 'a.v'})
        self.assertEqual(explain.enrich(d, {})[0]['title'], 'Latch inferred')


class TestTbgen(unittest.TestCase):
    def test_counter_testbench(self):
        src = open(os.path.join(ROOT, 'examples', '07_counter', 'counter.v')).read()
        m = vparse.parse_file(src)[0]
        name, text = tbgen.generate(m)
        self.assertEqual(name, 'tb_counter.v')
        for s in ('always #5 clk = ~clk;', '$dumpvars(0, tb_counter);', '$finish;', '.WIDTH(WIDTH)'):
            self.assertIn(s, text)


if __name__ == '__main__':
    unittest.main()
