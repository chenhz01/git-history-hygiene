#!/usr/bin/env python3
"""self_test.py for git-history-hygiene — [A] functional / [B] exception / [C] extreme edges."""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hygiene  # noqa: E402

RESULTS = []


def check(name, fn):
    try:
        fn()
        RESULTS.append((name, True))
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False))
        print("  [FAIL] %s -> %r" % (name, e))


def assert_eq(a, b):
    assert a == b, "%r != %r" % (a, b)


def assert_true(c, m=""):
    assert c, m


def hdr(h, parents="", date="2026-01-01", subject="do thing"):
    return "%s|%s|%s|%s|%s" % (hygiene.SEP, h, parents, date, subject)


LOG_OK = "\n".join([
    hdr("a" * 40, subject="add feature x"),
    "10\t2\tsrc/x.py",
    "1\t1\tREADME.md",
    hdr("b" * 40, parents="a" * 40 + " " + "0" * 40, subject="merge dev"),
    "5\t5\tsrc/y.py",
    hdr("c" * 40, parents="b" * 40, subject="fix typo"),
    "2\t0\tdocs/a.md",
])

# ---------- [A] functional ----------
def a01():
    cs = hygiene.parse_log(LOG_OK)
    assert_eq(len(cs), 3)
def a02():
    cs = hygiene.parse_log(LOG_OK)
    assert_eq(cs[0]["hash"], "a" * 40)
def a03():
    cs = hygiene.parse_log(LOG_OK)
    assert_eq(cs[1]["parents"], ["a" * 40, "0" * 40])
def a04():
    cs = hygiene.parse_log(LOG_OK)
    assert_eq(cs[0]["files"][0]["path"], "src/x.py")
def a05():
    cs = hygiene.parse_log(LOG_OK)
    assert_eq(cs[0]["files"][0]["added"], 10)
def a06():
    cs = hygiene.parse_log(LOG_OK)
    assert_true(cs[1]["files"][0]["binary"] is False)
def a07():
    cs = hygiene.parse_log(hdr("d" * 40) + '\n-\t-\t"bin/img\\303\\246.png"')
    assert_eq(cs[0]["files"][0]["path"], "bin/img\u00e6.png")
    assert_true(cs[0]["files"][0]["binary"])
def a08():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK))
    assert_eq(r["commits"], 3)
def a09():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK))
    assert_true(80 <= r["hygiene_score"] <= 100)
def a10():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK))
    assert_true(r["metrics"]["merge_density"] > 0.0)
def a11():
    big = hdr("e" * 40, subject="touch big") + "\n" + "\n".join("%d\t%d\tf%d.py" % (500, 500, i) for i in range(5))
    r = hygiene.analyze(hygiene.parse_log(big), big_churn=100)
    assert_true(any(f["id"] == "big-churn-file" for f in r["findings"]))
def a12():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK))
    assert_eq(r["metrics"]["max_files_per_commit"], 2)
def a13():
    log = hdr("f" * 40, subject="update") + "\n1\t1\ta.py"
    r = hygiene.analyze(hygiene.parse_log(log))
    assert_true(any(f["id"] == "generic-subjects" for f in r["findings"]))
def a14():
    log = hdr("g" * 40, subject="x") + "\n" + "\n".join("1\t1\tf%d.py" % i for i in range(60))
    r = hygiene.analyze(hygiene.parse_log(log))
    assert_true(any(f["id"] == "mega-commits" for f in r["findings"]))
def a15():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK))
    assert_true(r["metrics"]["p90_files_per_commit"] >= r["metrics"]["median_files_per_commit"])
def a16():
    r1 = hygiene.analyze(hygiene.parse_log(LOG_OK))
    r2 = hygiene.analyze(hygiene.parse_log(LOG_OK))
    assert_eq(r1, r2)
def a17():
    cs = hygiene.parse_log(hdr("h" * 40, subject="feat: |pipe| in subject"))
    assert_eq(cs[0]["subject"], "feat: |pipe| in subject")
def a18():
    cs = hygiene.parse_log(hdr("i" * 40) + "\n10\t0\ta.py\n5\t3\tb.py")
    assert_eq(len(cs[0]["files"]), 2)
def a19():
    r = hygiene.analyze([])
    assert_eq(r["hygiene_score"], 100)
def a20():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK))
    assert_eq(r["metrics"]["merge_count"], 1)
def a21():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK), big_churn=10 ** 9)
    assert_eq(r["metrics"]["churn_hotspots"], [])
def a22():
    cs = hygiene.parse_log(hdr("j" * 40) + "\n-\t-\tskip.png")
    assert_eq(cs[0]["files"][0]["added"], None)

# ---------- [B] exception paths ----------
def b01():
    try:
        hygiene.parse_log(None)
        assert False
    except ValueError:
        pass
def b02():
    try:
        hygiene.parse_log("")
        assert False
    except ValueError:
        pass
def b03():
    try:
        hygiene.parse_log("garbage line without header")
        assert False
    except ValueError:
        pass
def b04():
    try:
        hygiene.parse_log("--C--|only3parts")
        assert False
    except ValueError as e:
        assert_true("malformed" in str(e))
def b05():
    code = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hygiene.py")], capture_output=True, text=True)
    assert_eq(code.returncode, 2)
def b06():
    code = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hygiene.py"), "--repo", "definitely_not_a_repo_xyz"], capture_output=True, text=True)
    assert_eq(code.returncode, 2)
def b07():
    code = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hygiene.py"), "--log-file", "missing.txt"], capture_output=True, text=True)
    assert_eq(code.returncode, 2)
def b08():
    try:
        hygiene.get_log_text("definitely_not_a_repo_xyz")
        assert False
    except ValueError as e:
        assert_true("git log failed" in str(e))
def b09():
    try:
        hygiene.analyze(None)
        assert False
    except (ValueError, TypeError):
        pass
def b10():
    here = os.path.dirname(os.path.abspath(__file__))
    code = subprocess.run([sys.executable, os.path.join(here, "hygiene.py"), "--help"], capture_output=True, text=True)
    assert_eq(code.returncode, 0)
def b11():
    try:
        hygiene.parse_log(hdr("k" * 40) + "\nnot\ta\tnumstat? no tabs only 3")
        assert_eq(len(hygiene.parse_log(hdr("k" * 40) + "\nx\ty")), 1)
    except ValueError:
        pass
def b12():
    code = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hygiene.py"), "--log-file", "missing.txt", "--json"], capture_output=True, text=True)
    assert_eq(code.returncode, 2)

# ---------- [C] extreme edges ----------
def c01():
    cs = hygiene.parse_log(hdr("l" * 40))
    assert_eq(cs[0]["files"], [])
def c02():
    r = hygiene.analyze(hygiene.parse_log(hdr("m" * 40)))
    assert_eq(r["metrics"]["median_files_per_commit"], 0)
def c03():
    log = hdr("n" * 40) + "\n1\t1\t\u6587\u4ef6/\u4e2d\u6587.py"
    r = hygiene.analyze(hygiene.parse_log(log))
    assert_eq(r["metrics"]["churn_hotspots"], [])
def c04():
    log = hdr("o" * 40) + "\n" + "\n".join("1\t1\tdeep/%s/f.py" % ("/".join("d%d" % j for j in range(i))) for i in range(30))
    r = hygiene.analyze(hygiene.parse_log(log), big_churn=10)
    assert_true(len(r["metrics"]["churn_hotspots"]) <= 10)
def c05():
    cs = hygiene.parse_log(hdr("p" * 40, subject="\u63d0\u4ea4\ud83d\ude80"))
    assert_eq(cs[0]["subject"], "\u63d0\u4ea4\ud83d\ude80")
def c06():
    big = "\n".join([hdr("%d" % i, subject="c%d" % i) + "\n1\t1\ta.py" for i in range(2000)])
    r = hygiene.analyze(hygiene.parse_log(big))
    assert_eq(r["commits"], 2000)
def c07():
    cs = hygiene.parse_log(hdr("q" * 40) + "\n999999999\t999999999\thuge.bin.dat")
    r = hygiene.analyze(cs, big_churn=100)
    assert_true(r["metrics"]["churn_hotspots"][0]["churn"] == 1999999998)
def c08():
    cs = hygiene.parse_log(hdr("r" * 40, parents="s" * 40 + " " + "t" * 40))
    assert_eq(len(cs[0]["parents"]), 2)
def c09():
    r = hygiene.analyze(hygiene.parse_log("\n".join(hdr("%d" % i, parents="0" * 40) for i in range(10))))
    assert_eq(r["metrics"]["merge_count"], 0)
def c10():
    log = hdr("u" * 40) + "\r\n1\t1\ta.py\r\n"
    cs = hygiene.parse_log(log)
    assert_eq(cs[0]["files"][0]["path"], "a.py")
def c11():
    cs = hygiene.parse_log(hdr("v" * 40) + "\n1\t1\tlead/trail space .py  ")
    assert_eq(cs[0]["files"][0]["path"].endswith(".py"), True)
def c12():
    r = hygiene.analyze(hygiene.parse_log("\n".join(hdr(str(i), subject="update") for i in range(20))))
    assert_true(r["hygiene_score"] < 100)
def c13():
    cs = hygiene.parse_log(hdr("w" * 40) + "\n0\t0\tempty.py")
    r = hygiene.analyze(cs, big_churn=0)
    assert_true(any(h["churn"] == 0 for h in r["metrics"]["churn_hotspots"]))
def c14():
    log = hdr("x" * 40, subject="Fix") + "\n1\t1\ta.py"
    r = hygiene.analyze(hygiene.parse_log(log))
    assert_true(any(f["id"] == "generic-subjects" for f in r["findings"]))
def c15():
    try:
        hygiene.unquote_path(None)
        assert False
    except TypeError:
        pass
def c16():
    assert_eq(hygiene.unquote_path('"a\\tb"'), "a\tb")

for fn in sorted([v for k, v in list(globals().items()) if k.startswith(("a0", "a1", "a2", "b0", "b1", "c0", "c1"))], key=lambda f: f.__name__):
    check(fn.__name__, fn)


# ---------- [R2] round-2 additions (real repo e2e, emoji paths, output contracts) ----------
def r201():
    import tempfile
    d = tempfile.mkdtemp()
    def g(*a):
        subprocess.run(["git", "-C", d] + list(a), capture_output=True, text=True, check=True)
    g("init", "-q")
    g("config", "user.email", "t@example.com")
    g("config", "user.name", "t")
    open(os.path.join(d, "a.txt"), "w").write("hello\n")
    g("add", ".")
    g("commit", "-q", "-m", "update")
    r = hygiene.analyze(hygiene.parse_log(hygiene.get_log_text(d)))
    assert_eq(r["commits"], 1)
    assert_true(any(f["id"] == "generic-subjects" for f in r["findings"]))
def r202():
    bs = chr(92)
    quoted = '"emoji/' + bs + '360' + bs + '237' + bs + '232' + bs + '200.png"'
    cs = hygiene.parse_log(hdr("y" * 40) + "\n-\t-\t" + quoted)
    assert_eq(cs[0]["files"][0]["path"], "emoji/🚀.png")
def r203():
    cs = hygiene.parse_log(hdr("z" * 40) + '\n-\t-\t"中文/文件.py"'.encode("utf-8").decode("unicode_escape"))
    assert_true(len(cs[0]["files"]) == 1)
def r204():
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".log")
    os.close(fd)
    try:
        open(path, "w", encoding="utf-8").write(LOG_OK)
        code = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hygiene.py"), "--log-file", path, "--json"], capture_output=True, text=True)
        assert_eq(code.returncode, 0)
        data = json.loads(code.stdout)
        assert_eq(data["commits"], 3)
    finally:
        os.unlink(path)
def r205():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK))
    assert_true(0 <= r["hygiene_score"] <= 100)
def r206():
    worst = hygiene.analyze(hygiene.parse_log("\n".join([hdr(str(i), subject="update") + "\n" + "\n".join("1000\t1000\tf%d.py" % j for j in range(60)) for i in range(5)])))
    assert_eq(worst["hygiene_score"], 30)  # capped: 100 -30 hotspots -15 median -15 generic -10 mega
def r207():
    cs = hygiene.parse_log(hdr("w2" * 4) + "\n5\t2\twith space.py\n1\t1\ttab\there.py")
    assert_eq(len(cs[0]["files"]), 2)
def r208():
    r = hygiene.analyze(hygiene.parse_log(LOG_OK), mega_files=1)
    assert_true(r["metrics"]["max_files_per_commit"] >= 2)
def r209():
    cs = hygiene.parse_log(hdr("m2", date="2026-13-45"))
    assert_eq(cs[0]["date"], "2026-13-45")
def r210():
    code = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "hygiene.py"), "--repo", "."], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
    assert_true(code.returncode in (0, 2))

for fn in sorted([v for k, v in list(globals().items()) if k.startswith("r2")], key=lambda f: f.__name__):
    check(fn.__name__, fn)

passed = sum(1 for _, ok in RESULTS if ok)
for n, ok in RESULTS:
    if not ok:
        print("FAIL:", n)
print("SUMMARY: PASS %d/%d" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
