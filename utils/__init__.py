"""
Utils package - Contains utility functions and helpers.
"""

from utils.logger import Logger, get_logger, set_global_log_level, log_function_call, log_error, log_performance, PerformanceTimer
from utils.helpers import (
    ensure_directory_exists,
    get_file_extension,
    get_file_name_without_extension,
    find_files_by_extension,
    read_json_file,
    write_json_file,
    read_text_file,
    write_text_file,
    write_csv_file,
    sanitize_filename,
    format_file_size,
    build_markdown_report,
    build_text_report,
    save_all_formats,
    mask_sensitive_value,
    truncate_string,
    merge_dicts,
    chunk_list,
    flatten_dict
)

__all__ = [
    # Logger
    'Logger',
    'get_logger',
    'set_global_log_level',
    'log_function_call',
    'log_error',
    'log_performance',
    'PerformanceTimer',
    
    # Helpers
    'ensure_directory_exists',
    'get_file_extension',
    'get_file_name_without_extension',
    'find_files_by_extension',
    'read_json_file',
    'write_json_file',
    'read_text_file',
    'write_text_file',
    'write_csv_file',
    'sanitize_filename',
    'format_file_size',
    'build_markdown_report',
    'build_text_report',
    'save_all_formats',
    'mask_sensitive_value',
    'truncate_string',
    'merge_dicts',
    'chunk_list',
    'flatten_dict'
]
