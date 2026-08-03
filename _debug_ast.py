import ast

src = open(r"C:\Users\user\Desktop\Project-AIF-main\backend\runtime\fast_command_router.py", encoding="utf-8").read()
tree = ast.parse(src)

forbidden_calls = {
    "subprocess.run","subprocess.Popen","subprocess.call",
    "subprocess.check_call","subprocess.check_output",
    "os.system","os.popen","shutil.rmtree",
}
found = []
def _get_attr_name(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr); node = node.value
    if isinstance(node, ast.Name): parts.append(node.id)
    return ".".join(reversed(parts))

for node in ast.walk(tree):
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Attribute):
            full = _get_attr_name(node.func)
            if full in forbidden_calls:
                found.append((full, node.lineno))
        elif isinstance(node.func, ast.Name):
            if node.func.id in {"system","popen","rmtree"}:
                found.append((node.func.id, node.lineno))
print("FORBIDDEN:", found)
print("shell=True:", "shell=True" in src, "| shell = True:", "shell = True" in src)