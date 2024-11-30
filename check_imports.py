# check_imports.py
import os
import re

def check_file_imports(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Look for import statements
    import_patterns = [
        r'from\s+([\w.]+)\s+import',  # from x import y
        r'import\s+([\w.]+)'          # import x
    ]
    
    found_imports = []
    for pattern in import_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            import_path = match.group(1)
            if 'src.' in import_path:
                found_imports.append(import_path)
    
    return found_imports

def scan_directory():
    print("Scanning for import statements...")
    print("-" * 50)
    
    problematic_files = []
    
    for root, _, files in os.walk('.'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                imports = check_file_imports(file_path)
                
                # Check for the problematic import
                for imp in imports:
                    if 'src.signals.providers.moving_average' in imp and not imp.endswith('_provider'):
                        problematic_files.append({
                            'file': file_path,
                            'import': imp
                        })
                        
                if imports:
                    print(f"\nFile: {file_path}")
                    for imp in imports:
                        print(f"  Import: {imp}")
                        if 'moving_average' in imp:
                            print(f"    ⚠️ Check this import!")
    
    if problematic_files:
        print("\n" + "!" * 50)
        print("Problematic imports found:")
        for item in problematic_files:
            print(f"\nFile: {item['file']}")
            print(f"Incorrect import: {item['import']}")
            print("Should be: src.signals.providers.moving_average_provider")
    else:
        print("\nNo problematic imports found.")

if __name__ == "__main__":
    scan_directory()