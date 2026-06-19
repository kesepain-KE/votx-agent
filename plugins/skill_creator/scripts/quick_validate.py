"""
Quick validation script for skills - minimal version
"""

import sys
import os
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


class FrontmatterParseError(Exception):
    """Raised when SKILL.md frontmatter cannot be parsed."""


def _strip_yaml_scalar(value):
    """Strip common one-line YAML scalar quoting."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    if value in ("{}", "null", "~"):
        return {} if value == "{}" else None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    return value


def _parse_frontmatter_simple(frontmatter_text):
    """Parse the simple YAML subset normally used by SKILL.md frontmatter.

    This fallback keeps quick_validate usable when PyYAML is not installed. It
    supports top-level key/value pairs, one-level nested maps, and literal or
    folded block scalars.
    """
    result = {}
    lines = frontmatter_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():
            raise FrontmatterParseError(f"Unexpected indented line: {line}")
        if ":" not in line:
            raise FrontmatterParseError(f"Invalid YAML line: {line}")

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise FrontmatterParseError("Empty YAML key")

        if value in ("|", ">"):
            block_lines = []
            while i < len(lines) and (lines[i][:1].isspace() or not lines[i].strip()):
                block_lines.append(lines[i].strip())
                i += 1
            text = "\n".join(block_lines).strip()
            result[key] = " ".join(text.split()) if value == ">" else text
            continue

        if not value:
            nested = {}
            while i < len(lines) and (lines[i][:1].isspace() or not lines[i].strip()):
                nested_line = lines[i]
                i += 1
                if not nested_line.strip() or nested_line.lstrip().startswith("#"):
                    continue
                if ":" not in nested_line:
                    raise FrontmatterParseError(f"Invalid nested YAML line: {nested_line}")
                nested_key, nested_value = nested_line.split(":", 1)
                nested[nested_key.strip()] = _strip_yaml_scalar(nested_value)
            result[key] = nested
            continue

        result[key] = _strip_yaml_scalar(value)

    return result


def parse_frontmatter(frontmatter_text):
    """Parse SKILL.md frontmatter with PyYAML when available, fallback otherwise."""
    if yaml is not None:
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise FrontmatterParseError(f"Invalid YAML in frontmatter: {e}") from e
    else:
        frontmatter = _parse_frontmatter_simple(frontmatter_text)

    if not isinstance(frontmatter, dict):
        raise FrontmatterParseError("Frontmatter must be a YAML dictionary")
    return frontmatter


def validate_skill(skill_path):
    """Basic validation of a skill"""
    skill_path = Path(skill_path)

    # Check SKILL.md exists
    skill_md = skill_path / 'SKILL.md'
    if not skill_md.exists():
        return False, "SKILL.md not found"

    # Read and validate frontmatter
    content = skill_md.read_text(encoding="utf-8")
    if not content.startswith('---'):
        return False, "No YAML frontmatter found"

    # Extract frontmatter
    match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    try:
        frontmatter = parse_frontmatter(frontmatter_text)
    except FrontmatterParseError as e:
        return False, str(e)

    # Define allowed properties
    ALLOWED_PROPERTIES = {'name', 'description', 'license', 'allowed-tools', 'metadata', 'version', 'category', 'enabled', 'override', 'compatibility', 'source', 'author', 'homepage', 'tags', 'slug'}

    # Check for unexpected properties (excluding nested keys under metadata)
    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        return False, (
            f"Unexpected key(s) in SKILL.md frontmatter: {', '.join(sorted(unexpected_keys))}. "
            f"Allowed properties are: {', '.join(sorted(ALLOWED_PROPERTIES))}"
        )

    # Check required fields
    if 'name' not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if 'description' not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    # Extract name for validation
    name = frontmatter.get('name', '')
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        # Check naming convention (case-insensitive, letters/digits/hyphens/underscores)
        if not re.match(r'(?i)^[a-z0-9_-]+$', name):
            return False, f"Name '{name}' should contain only letters, digits, hyphens, and underscores"
        if name.startswith(('-', '_')) or name.endswith(('-', '_')) or '--' in name or '__' in name:
            return False, f"Name '{name}' cannot start/end with hyphen/underscore or contain consecutive hyphens/underscores"
        # Check name length (max 64 characters per spec)
        if len(name) > 64:
            return False, f"Name is too long ({len(name)} characters). Maximum is 64 characters."

    # Extract and validate description
    description = frontmatter.get('description', '')
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        # Check for angle brackets
        if '<' in description or '>' in description:
            return False, "Description cannot contain angle brackets (< or >)"
        # Check description length (max 1024 characters per spec)
        if len(description) > 1024:
            return False, f"Description is too long ({len(description)} characters). Maximum is 1024 characters."

    return True, "Skill is valid!"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)
    
    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
