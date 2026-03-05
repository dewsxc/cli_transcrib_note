import os
import sys
import re
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Mapping of Chinese numerals to integers
CHINESE_NUM_MAP = {
    '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
    '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
    '十': 10
}

DATE_FORMATS = [
    "%Y%m%d",
    "%Y_%m_%d",
    "%Y-%m-%d"
]

def chinese_to_int(s):
    """
    Simplistic conversion of Chinese numerals (0-99) to integers.
    Handles '一', '十', '十一', '二十', '二十一' etc.
    """
    if not s:
        return None
    
    # Simple cases 0-10
    if len(s) == 1 and s in CHINESE_NUM_MAP:
        return CHINESE_NUM_MAP[s]
    
    # Cases like '十一' (11) or '二十' (20) or '二十一' (21)
    if '十' in s:
        parts = s.split('十')
        res = 0
        # Prefix: '二十' -> parts[0] is '二'
        if parts[0]:
            res += CHINESE_NUM_MAP.get(parts[0], 0) * 10
        else:
            # '十' or '十一' -> res starts with 10
            res += 10
        # Suffix: '十一' -> parts[1] is '一'
        if len(parts) > 1 and parts[1]:
            res += CHINESE_NUM_MAP.get(parts[1], 0)
        return res
    
    return CHINESE_NUM_MAP.get(s, None)

def parse_date(filename):
    """Try to parse date from filename stem using supported formats."""
    name = Path(filename).stem
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(name, fmt)
        except ValueError:
            continue
    return None

def is_date_filename(filename):
    """Check if filename matches any of the supported date formats."""
    return parse_date(filename) is not None

def get_year_from_date_filename(filename):
    """Extract %Y from date filename."""
    dt = parse_date(filename)
    if dt:
        return dt.strftime("%Y")
    return None

def natural_sort_key(s):
    """
    Key for natural sorting. 
    Handles Arabic numbers and Chinese numerals (第[一二三...]课/课).
    """
    pattern = r'([0-9]+|[一二三四五六七八九十]+)'
    segments = re.split(pattern, s)
    
    key = []
    for part in segments:
        if not part:
            continue
        if part.isdigit():
            key.append(int(part))
        else:
            c_val = chinese_to_int(part)
            if c_val is not None:
                key.append(c_val)
            else:
                key.append(part.lower())
    return key

def remove_markdown(text):
    """
    Remove basic Markdown formatting from text.
    - Headers (#)
    - Bold/Italic (*, _, **)
    - Links [text](url) -> text
    - Code blocks and inline code
    - Comments <!-- ... -->
    """
    # Remove HTML/Markdown comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Remove code blocks
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    
    # Remove inline code
    text = re.sub(r'`(.*?)`', r'\1', text)
    
    # Remove headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    
    # Remove bold and italic
    text = re.sub(r'(\*\*|__)(.*?)\1', r'\2', text)
    text = re.sub(r'(\*|_)(.*?)\1', r'\2', text)
    
    # Remove links [text](url) -> text
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    
    # Remove horizontal rules
    text = re.sub(r'^---$', '', text, flags=re.MULTILINE)
    
    return text.strip()

def write_concatenated_file(output_path, files, source_dir, strip_markdown=False):
    """Helper to write multiple files into one."""
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as outfile:
        for i, filename in enumerate(files):
            filepath = os.path.join(source_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as infile:
                content = infile.read()
                
                if strip_markdown:
                    content = remove_markdown(content)
                else:
                    outfile.write(f"# Source: {filename}\n\n")
                
                outfile.write(content)
                
                if i < len(files) - 1:
                    if strip_markdown:
                        outfile.write("\n\n" + "="*40 + "\n\n")
                    else:
                        outfile.write("\n\n---\n\n") # Separator between files
    print(f"Concatenated {len(files)} files into {output_path}")

def concat_md_files(directory_path, output_path=None, test_mode=False, extension='.md'):
    if not os.path.isdir(directory_path):
        print(f"Error: {directory_path} is not a valid directory.")
        return

    directory_path = os.path.normpath(directory_path)
    dir_name = os.path.basename(directory_path)
    
    # Normalize extension (ensure it starts with .)
    if not extension.startswith('.'):
        extension = '.' + extension
        
    strip_markdown = (extension.lower() != '.md')

    # Get all .md files
    md_files = [f for f in os.listdir(directory_path) if f.endswith('.md')]
    
    if not md_files:
        print("No .md files found in the directory.")
        return

    # Separate date-named files and others
    date_files_with_dt = []
    other_files = []
    
    for f in md_files:
        dt = parse_date(f)
        if dt:
            date_files_with_dt.append((f, dt))
        else:
            other_files.append(f)

    # 1. Sort date files by actual date object (oldest to latest)
    date_files_with_dt.sort(key=lambda x: x[1])
    date_files = [x[0] for x in date_files_with_dt]

    # 2. Sort other files by natural/meaningful order
    other_files.sort(key=natural_sort_key)

    # Group sorted date files by year
    date_files_by_year = defaultdict(list)
    for f, dt in date_files_with_dt:
        year = dt.strftime("%Y")
        date_files_by_year[year].append(f)

    # Determine actions
    if test_mode:
        print(f"Test Mode: Source directory: '{directory_path}'")
        print(f"Target extension: '{extension}' (Strip Markdown: {strip_markdown})")
        if date_files:
            print("\nDate-named files grouped by year (sorted chronologically):")
            for year in sorted(date_files_by_year.keys()):
                print(f"  Year {year}:")
                for f in date_files_by_year[year]:
                    print(f"    - {f}")
        if other_files:
            print("\nOther files (natural order):")
            for f in other_files:
                print(f"    - {f}")
        
        # Show where they WOULD be saved
        print("\nTarget output(s):")
        if output_path:
            if os.path.isdir(output_path):
                for year in sorted(date_files_by_year.keys()):
                    print(f"  - {os.path.join(output_path, f'{year}{extension}')}")
                if other_files:
                    print(f"  - {os.path.join(output_path, f'{dir_name}{extension}')}")
            else:
                print(f"  - {output_path} (All files combined)")
        else:
            print(f"  - {os.path.join(directory_path, f'combined_notes{extension}')} (All files combined)")
        return

    # Execution Mode
    if output_path:
        if os.path.isdir(output_path):
            # If output is a directory, use year for date-named files
            for year, files in date_files_by_year.items():
                year_output = os.path.join(output_path, f"{year}{extension}")
                write_concatenated_file(year_output, files, directory_path, strip_markdown)
            
            # For other files, use the directory name
            if other_files:
                other_output = os.path.join(output_path, f"{dir_name}{extension}")
                write_concatenated_file(other_output, other_files, directory_path, strip_markdown)
        else:
            # If output is a specific file, combine EVERYTHING
            all_files = date_files + other_files
            write_concatenated_file(output_path, all_files, directory_path, strip_markdown)
    else:
        # Default: combined_notes.{ext} in source directory
        all_files = date_files + other_files
        default_output = os.path.join(directory_path, f"combined_notes{extension}")
        write_concatenated_file(default_output, all_files, directory_path, strip_markdown)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Concatenate .md files in a directory.")
    parser.add_argument("directory", help="Path to the directory containing .md files.")
    parser.add_argument("-t", "--test", action="store_true", help="Test mode: only print the order of files.")
    parser.add_argument("-o", "--output", help="Output path. If directory, date files use year for name. If file path, uses it.")
    parser.add_argument("-x", "--extension", default=".md", help="Target file extension (default: .md). If not .md, markdown format is removed.")
    
    args = parser.parse_args()
    
    concat_md_files(args.directory, output_path=args.output, test_mode=args.test, extension=args.extension)
