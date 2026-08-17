"""
Helpers - Common utility functions for the application.
Contains file operations, string manipulation, and other helper utilities.
"""

import os
import json
import csv
import io
from typing import Dict, Any, List, Optional
from pathlib import Path


def ensure_directory_exists(directory_path: str) -> None:
    """
    Ensure that a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory
    """
    os.makedirs(directory_path, exist_ok=True)


def get_file_extension(file_path: str) -> str:
    """
    Get the file extension from a file path.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File extension (including the dot, e.g., '.pdf')
    """
    return os.path.splitext(file_path)[1].lower()


def get_file_name_without_extension(file_path: str) -> str:
    """
    Get the file name without extension from a file path.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File name without extension
    """
    return os.path.splitext(os.path.basename(file_path))[0]


def find_files_by_extension(directory: str, extensions: List[str]) -> List[str]:
    """
    Find all files with specified extensions in a directory.
    
    Args:
        directory: Directory to search
        extensions: List of file extensions (e.g., ['.pdf', '.jpg'])
        
    Returns:
        List of file paths
    """
    found_files = []
    
    if not os.path.exists(directory):
        return found_files
    
    extensions_lower = [ext.lower() for ext in extensions]
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if get_file_extension(file) in extensions_lower:
                found_files.append(os.path.join(root, file))
    
    return found_files


def read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Read and parse a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Parsed JSON data or None if failed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading JSON file {file_path}: {e}")
        return None


def write_json_file(file_path: str, data: Dict[str, Any], indent: int = 2) -> bool:
    """
    Write data to a JSON file.
    
    Args:
        file_path: Path to the output file
        data: Data to write
        indent: JSON indentation level
        
    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_directory_exists(os.path.dirname(file_path))
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error writing JSON file {file_path}: {e}")
        return False


def read_text_file(file_path: str) -> Optional[str]:
    """
    Read a text file.
    
    Args:
        file_path: Path to the text file
        
    Returns:
        File content or None if failed
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading text file {file_path}: {e}")
        return None


def write_text_file(file_path: str, content: str) -> bool:
    """
    Write content to a text file.
    
    Args:
        file_path: Path to the output file
        content: Content to write
        
    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_directory_exists(os.path.dirname(file_path))
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Error writing text file {file_path}: {e}")
        return False


def write_csv_file(file_path: str, data: List[Dict[str, Any]]) -> bool:
    """
    Write data to a CSV file.
    
    Args:
        file_path: Path to the output CSV file
        data: List of dictionaries to write
        
    Returns:
        True if successful, False otherwise
    """
    try:
        ensure_directory_exists(os.path.dirname(file_path))
        
        if not data:
            return True
        
        fieldnames = list(data[0].keys())
        
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        
        return True
    except Exception as e:
        print(f"Error writing CSV file {file_path}: {e}")
        return False


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing invalid characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Formatted size string (e.g., '1.5 MB')
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def build_markdown_report(name: str, extracted: dict, adi_dict: dict = None) -> str:
    """
    Build a markdown report from extracted data.
    
    Args:
        name: Document name
        extracted: Extracted field data
        adi_dict: Optional ADI analysis results
        
    Returns:
        Markdown formatted string
    """
    lines = [f"# {name}", "", "## Extracted Fields", ""]
    
    for k, v in extracted.items():
        if k in ("created_at", "updated_at", "id", "validation"):
            continue
        display = v if v is not None else "_null_"
        lines.append(f"- **{k}**: {display}")
    
    if adi_dict:
        ar = adi_dict.get("analyzeResult", {})
        tables = ar.get("tables", [])
        
        if tables:
            lines += ["", "---", "", "## Tables", ""]
            for ti, table in enumerate(tables):
                lines.append(f"### Table {ti+1} ({table.get('rowCount')}r × {table.get('columnCount')}c)")
                lines.append("")
                
                cells = table.get("cells", [])
                grid = {}
                for cell in cells:
                    r, c = cell.get("rowIndex", 0), cell.get("columnIndex", 0)
                    grid[(r, c)] = cell.get("content", "").replace("\n", " ")
                
                if grid:
                    rows = max(r for r, _ in grid) + 1
                    cols = max(c for _, c in grid) + 1
                    
                    header = "| " + " | ".join(grid.get((0, c), "") for c in range(cols)) + " |"
                    sep = "| " + " | ".join("---" for _ in range(cols)) + " |"
                    lines += [header, sep]
                    
                    for r in range(1, rows):
                        lines.append("| " + " | ".join(grid.get((r, c), "") for c in range(cols)) + " |")
                lines.append("")
        
        content = ar.get("content", "")
        if content:
            lines += ["", "---", "", "## Full Document Text", "", "```"]
            lines += content.splitlines()
            lines.append("```")
    
    return "\n".join(lines)


def build_text_report(extracted: dict, adi_dict: dict = None) -> str:
    """
    Build a plain text report from extracted data.
    
    Args:
        extracted: Extracted field data
        adi_dict: Optional ADI analysis results
        
    Returns:
        Plain text formatted string
    """
    content = ""
    if adi_dict:
        content = adi_dict.get("analyzeResult", {}).get("content", "")
    
    lines = ["=" * 60, "EXTRACTED FIELDS", "=" * 60]
    for k, v in extracted.items():
        if k in ("created_at", "updated_at", "id", "validation"):
            continue
        lines.append(f"{k:<45}: {v if v is not None else ''}")
    
    if content:
        lines += ["", "=" * 60, "FULL DOCUMENT TEXT", "=" * 60, "", content]
    
    return "\n".join(lines)


def save_all_formats(name: str, extracted: dict, adi_dict: dict = None, 
                    output_dir: str = "Extracted") -> None:
    """
    Save extracted data in multiple formats.
    
    Args:
        name: Document name
        extracted: Extracted field data
        adi_dict: Optional ADI analysis results
        output_dir: Base output directory
    """
    folder = os.path.join(output_dir, name)
    ensure_directory_exists(folder)
    
    # Save JSON
    write_json_file(os.path.join(folder, f"{name}_extracted.json"), extracted)
    
    # Save text report
    text_report = build_text_report(extracted, adi_dict)
    write_text_file(os.path.join(folder, f"{name}.txt"), text_report)
    
    # Save markdown report
    md_report = build_markdown_report(name, extracted, adi_dict)
    write_text_file(os.path.join(folder, f"{name}.md"), md_report)
    
    # Save CSV
    write_csv_file(os.path.join(folder, f"{name}.csv"), [extracted])
    
    # Save raw ADI JSON if available
    if adi_dict:
        write_json_file(os.path.join(folder, f"{name}_adi_raw.json"), adi_dict)


def mask_sensitive_value(value: str, visible_chars: int = 2) -> str:
    """
    Mask a sensitive value by showing only a few characters.
    
    Args:
        value: Value to mask
        visible_chars: Number of characters to show at start and end
        
    Returns:
        Masked value
    """
    if not value or len(value) <= visible_chars * 2:
        return "*" * len(value) if value else ""
    
    return value[:visible_chars] + "*" * (len(value) - visible_chars * 2) + value[-visible_chars:]


def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length.
    
    Args:
        text: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple dictionaries, with later dictionaries taking precedence.
    
    Args:
        *dicts: Dictionaries to merge
        
    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def chunk_list(items: List[Any], chunk_size: int) -> List[List[Any]]:
    """
    Split a list into chunks of specified size.
    
    Args:
        items: List to chunk
        chunk_size: Size of each chunk
        
    Returns:
        List of chunks
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
    """
    Flatten a nested dictionary.
    
    Args:
        d: Dictionary to flatten
        parent_key: Parent key for nested items
        sep: Separator between keys
        
    Returns:
        Flattened dictionary
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)
