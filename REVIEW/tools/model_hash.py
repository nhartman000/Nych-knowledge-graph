"""SHA256 over every file of the installed en_core_web_sm package (sorted relative paths). --write F | --check F"""
import hashlib, sys, pathlib, en_core_web_sm
root = pathlib.Path(en_core_web_sm.__file__).parent
h = hashlib.sha256()
for p in sorted(x for x in root.rglob("*") if x.is_file() and "__pycache__" not in x.parts):
    h.update(str(p.relative_to(root)).encode()); h.update(hashlib.sha256(p.read_bytes()).digest())
line = f"{h.hexdigest()}  en_core_web_sm-{en_core_web_sm.__version__} (tree hash; wheel sha256 1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85)"
if len(sys.argv) > 2 and sys.argv[1] == "--write": open(sys.argv[2], "w").write(line + "\n"); print(line)
elif len(sys.argv) > 2 and sys.argv[1] == "--check":
    want = open(sys.argv[2]).read().split()[0]; print(line); sys.exit(0 if want == h.hexdigest() else 1)
else: print(line)
