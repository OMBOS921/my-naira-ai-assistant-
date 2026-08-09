import os
import sys

FORBIDDEN_IMPORTS = {
    'win32gui', 'win32api', 'win32com', 'pywin32',
    'Xlib', 'quartz', 'Quartz',
    'apt', 'pacman', 'dnf', 'winget', 'brew',
    'gi.repository.Gtk', 'ydotool', 'xdotool',
}

def check_file(filepath: str) -> list[str]:
    violations = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line_str = line.strip()
            # Simple check, real linter would use AST
            if line_str.startswith('import ') or line_str.startswith('from '):
                for forbidden in FORBIDDEN_IMPORTS:
                    if forbidden in line_str.split():
                        violations.append(f"Line {i}: {line_str}")
    return violations

EXCLUSIONS = {
    '_production_adapter.py',
    '_screen_capture.py',
}

def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    backend_dir = os.path.join(root_dir, 'backend')
    adapters_dir = os.path.join(backend_dir, 'platform', 'adapters')
    
    total_violations = 0
    for dirpath, dirnames, filenames in os.walk(backend_dir):
        if dirpath.startswith(adapters_dir):
            continue  # Adapters are allowed to use OS-specific imports
        for filename in filenames:
            if filename in EXCLUSIONS:
                continue
            if filename.endswith('.py'):
                filepath = os.path.join(dirpath, filename)
                violations = check_file(filepath)
                if violations:
                    print(f"PAL Boundary Violation in {os.path.relpath(filepath, root_dir)}:")
                    for v in violations:
                        print(f"  {v}")
                    total_violations += len(violations)
                    
    if total_violations > 0:
        print(f"\nFailed: Found {total_violations} PAL boundary violations outside backend/platform/adapters.")
        sys.exit(1)
    else:
        print("Success: No PAL boundary violations found.")

if __name__ == '__main__':
    main()
