"""Q-010: compare type/method names from the installed (modded) HDT with upstream source at the same version.

Prerequisite: run MetadataProbe first (writes out/metadata/types.txt, bobsbuddyinvoker_methods.txt).
Usage:  python compare_types.py [upstream-rev]   (default ef8ab6e8 = upstream commit "v1.58.1")
Writes: out/metadata/types_not_in_upstream.txt
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import srctemplates

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "metadata")


def main():
    rev = sys.argv[1] if len(sys.argv) > 1 else "ef8ab6e8"
    grep = subprocess.run(
        ["git", "-C", srctemplates.HDT_REPO, "grep", "-h", "-o", "-E",
         r'(class|struct|enum|interface|record)\s+\w+|x:Class="[A-Za-z0-9_.]+"', rev, "--", "*.cs", "*.xaml"],
        capture_output=True, check=True).stdout.decode("utf-8", "replace")
    declared = set()
    for line in grep.splitlines():
        m = re.search(r"(?:class|struct|enum|interface|record)\s+(\w+)", line) or \
            re.search(r'x:Class="(?:\w+\.)*(\w+)"', line)
        if m:
            declared.add(m.group(1))

    types = [l.strip() for l in open(os.path.join(OUT, "types.txt"), encoding="utf-8")]
    missing = []
    for t in types:
        if "<" in t or t.startswith("XamlGeneratedNamespace"):
            continue
        simple = re.sub(r"`\d+$", "", re.split(r"[.+]", t)[-1])
        if simple not in declared:
            missing.append(t)

    src = srctemplates.git_show(rev)
    methods = sorted({l.split(" (")[0] for l in open(os.path.join(OUT, "bobsbuddyinvoker_methods.txt"), encoding="utf-8")})
    extra_methods = []
    for m in methods:
        if m in (".ctor", ".cctor"):
            continue
        name = re.sub(r"^<(\w+)>.*", r"\1", re.sub(r"^(get_|set_|add_|remove_)", "", m))
        if not re.search(r"\b" + re.escape(name) + r"\b", src):
            extra_methods.append(m)

    with open(os.path.join(OUT, "types_not_in_upstream.txt"), "w", encoding="utf-8") as fh:
        fh.write(f"# installed types={len(types)}, upstream({rev}) declared names={len(declared)}\n")
        fh.write("# types whose simple name is not declared anywhere in upstream source:\n")
        fh.writelines(t + "\n" for t in missing)
        fh.write("# BobsBuddyInvoker members not found in upstream BobsBuddyInvoker.cs:\n")
        fh.writelines(m + "\n" for m in extra_methods)
    print(f"types={len(types)} not_in_upstream={len(missing)} invoker_extra={extra_methods}")
    for t in missing:
        print("  ", t)


if __name__ == "__main__":
    main()
