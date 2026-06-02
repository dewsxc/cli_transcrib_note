import os
import re
import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Default source directory for STT-produced .srt files.
# Mirrors ServiceSetup.audio_dir (work_dir/tmp/audio); the script lives in work_dir.
DEFAULT_SRT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp", "audio")

# Delimiter separating the channel name from the title in STT filenames,
# e.g. "All-In Podcast - Some Episode Title.srt".
CHANNEL_DELIMITER = " - "

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

    # Remove unordered list markers (-, *, +)
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)

    # Remove ordered list markers (1. 2. etc.)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # Collapse multiple blank lines into one
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def write_concatenated_file(output_path, files, source_dir):
    """Helper to write multiple files into one."""
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as outfile:
        for i, filename in enumerate(files):
            filepath = os.path.join(source_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as infile:
                content = infile.read()
                content = remove_markdown(content)
                outfile.write(f"## {filename}\n{content}")
                if i < len(files) - 1:
                    outfile.write("\n\n")
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

    # Get all files matching the target extension
    md_files = [f for f in os.listdir(directory_path) if f.endswith(extension)]

    if not md_files:
        print(f"No '{extension}' files found in the directory.")
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
        print(f"Target extension: '{extension}'")
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
                write_concatenated_file(year_output, files, directory_path)
            
            # For other files, use the directory name
            if other_files:
                other_output = os.path.join(output_path, f"{dir_name}{extension}")
                write_concatenated_file(other_output, other_files, directory_path)
        else:
            # If output is a specific file, combine EVERYTHING
            all_files = date_files + other_files
            write_concatenated_file(output_path, all_files, directory_path)
    else:
        # Default: combined_notes.{ext} in source directory
        all_files = date_files + other_files
        default_output = os.path.join(directory_path, f"combined_notes{extension}")
        write_concatenated_file(default_output, all_files, directory_path)

def channel_name_from_filename(filename):
    """
    Extract the channel name from a STT filename.
    Files are named "<channel> - <title>.<ext>", so the channel is the part
    before the first ' - '. Files without the delimiter use their whole stem.
    """
    stem = Path(filename).stem
    if CHANNEL_DELIMITER in stem:
        return stem.split(CHANNEL_DELIMITER, 1)[0].strip()
    return stem.strip()

def safe_filename(name):
    """Make a channel name safe to use as a filename."""
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "untitled"

# A SubRip timestamp, e.g. "00:00:01,000 --> 00:00:04,500" (',' or '.' for ms).
# Matched anywhere on the line, since some files prefix the sequence number
# on the same line, e.g. "1 00:00:00,320 --> 00:01:22,260".
SRT_TIMESTAMP_RE = re.compile(r'\d{2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{1,3}')

def srt_to_plain_text(content):
    """
    Strip SubRip markup, leaving only the spoken text:
    drop sequence numbers, timestamp lines and blank separators.
    """
    lines = []
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.isdigit():                 # sequence number
            continue
        if SRT_TIMESTAMP_RE.search(line):  # timestamp line (with or without index)
            continue
        lines.append(line)
    return "\n".join(lines)

def write_channel_merge(output_path, channel, files, source_dir):
    """Merge the given files (already time-ordered) into one file per channel."""
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as outfile:
        outfile.write(f"# {channel}\n\n")
        for i, filename in enumerate(files):
            filepath = os.path.join(source_dir, filename)
            with open(filepath, 'r', encoding='utf-8') as infile:
                content = infile.read()
            # Subtitle sources: keep only the text, drop timestamps/sequence numbers.
            if filename.lower().endswith('.srt'):
                content = srt_to_plain_text(content)
            content = content.strip()
            # File name goes first, marking the start of this file's content.
            outfile.write(f"## {filename}\n\n{content}\n")
            if i < len(files) - 1:
                outfile.write("\n")
    print(f"Merged {len(files)} files into {output_path}")

def merge_channel_files(source_path, output_dir=None, test_mode=False, extension='.srt', channel_filter=None):
    """
    Group files in source_path by channel name and merge each channel's files,
    in chronological order (by modification time), into a single output file.

    If channel_filter is given, only channels whose name contains it
    (case-insensitive substring match) are merged.
    """
    if not os.path.isdir(source_path):
        print(f"Error: {source_path} is not a valid directory.")
        return

    source_path = os.path.normpath(source_path)

    # Normalize extension (ensure it starts with .)
    if not extension.startswith('.'):
        extension = '.' + extension

    files = [
        f for f in os.listdir(source_path)
        if f.endswith(extension) and os.path.isfile(os.path.join(source_path, f))
    ]

    if not files:
        print(f"No '{extension}' files found in {source_path}.")
        return

    # Group by channel name, keeping each file's modification time for ordering.
    channels = defaultdict(list)
    for f in files:
        channel = channel_name_from_filename(f)
        mtime = os.path.getmtime(os.path.join(source_path, f))
        channels[channel].append((f, mtime))

    # Optionally narrow to channels matching the filter.
    if channel_filter:
        matched = {c: v for c, v in channels.items() if channel_filter.lower() in c.lower()}
        if not matched:
            print(f"No channel matching '{channel_filter}' found in {source_path}.")
            print("Available channels: " + ", ".join(sorted(channels)))
            return
        channels = matched

    # Sort each channel's files chronologically (oldest first).
    for channel in channels:
        channels[channel].sort(key=lambda x: x[1])

    if not output_dir:
        output_dir = os.path.join(source_path, "merged_channels")

    if test_mode:
        print(f"Test Mode: Source directory: '{source_path}'")
        print(f"Target extension: '{extension}'")
        print(f"Output directory: '{output_dir}'")
        print(f"\nFound {len(channels)} channel(s):")
        for channel in sorted(channels):
            entries = channels[channel]
            print(f"\n  [{channel}] -> {os.path.join(output_dir, safe_filename(channel) + '.md')} ({len(entries)} files)")
            for f, mtime in entries:
                stamp = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                print(f"    - {stamp}  {f}")
        return

    for channel in sorted(channels):
        ordered_files = [f for f, _ in channels[channel]]
        output_path = os.path.join(output_dir, f"{safe_filename(channel)}.md")
        write_channel_merge(output_path, channel, ordered_files, source_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Concatenate or merge transcription files.")
    # Global options (place before the subcommand).
    parser.add_argument("-t", "--test", action="store_true", help="Test mode: only print the planned actions.")
    parser.add_argument("-x", "--extension", default=".srt", help="Target file extension (global, default: .srt).")
    parser.add_argument("-o", "--output", help="Output path. merge_channel: output directory. concat: output file or directory.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # concat: original behaviour (group date-named files, natural-sort the rest)
    concat_parser = subparsers.add_parser("concat", help="Concatenate files in a directory.")
    concat_parser.add_argument("directory", help="Path to the directory containing the files.")

    # merge_channel: merge all files sharing the same channel name
    merge_parser = subparsers.add_parser(
        "merge_channel",
        help="Merge all files sharing the same channel name (prefix before ' - ').",
    )
    merge_parser.add_argument(
        "channel", nargs="?",
        help="Optional channel-name filter (case-insensitive substring). Merge only matching channels.",
    )
    merge_parser.add_argument(
        "-p", "--path", default=DEFAULT_SRT_DIR,
        help="Source directory. Defaults to the STT .srt output dir (tmp/audio).",
    )

    args = parser.parse_args()

    output = os.path.expanduser(args.output) if args.output else None

    if args.command == "merge_channel":
        merge_channel_files(
            os.path.expanduser(args.path),
            output_dir=output,
            test_mode=args.test,
            extension=args.extension,
            channel_filter=args.channel,
        )
    elif args.command == "concat":
        concat_md_files(
            args.directory,
            output_path=output,
            test_mode=args.test,
            extension=args.extension,
        )
