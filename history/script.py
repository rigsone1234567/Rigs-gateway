import yaml

# Sample YAML data as a string
yaml_data = """
project:
  name: My Termux App
  version: 1.0.0
  dependencies:
    - python
    - pyyaml
"""

# Parse the YAML data into a Python dictionary
data = yaml.safe_load(yaml_data)

print("Successfully loaded YAML data!")
print(f"Project Name: {data['project']['name']}")

