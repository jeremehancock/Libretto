#!/usr/bin/env python3

# Libretto: A Plex Library Export Tool
# Exports movie, TV show, and music libraries from Plex Media Server to CSV format
#
# Developed by Jereme Hancock
# https://github.com/jeremehancock/Libretto
#
# MIT License
#
# Copyright (c) 2024 Jereme Hancock
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import re
import sys
import argparse
import logging
import csv
import html
import time
import signal
import unicodedata
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import xml.etree.ElementTree as ET
from colorama import init, Fore, Back, Style

# Initialize
init(autoreset=True)

class CrossPlatformLock:
    """A cross-platform file locking mechanism."""
    
    def __init__(self, lock_file):
        self.lock_file = Path(lock_file)
        self.lock_file_handle = None
        self._lock = threading.Lock()
    
    def acquire(self):
        """Acquire a lock. Returns True if successful, False if already locked."""
        with self._lock:
            if self.lock_file.exists():
                try:
                    # Check if the process ID in the lock file still exists
                    with open(self.lock_file, 'r') as f:
                        pid = int(f.read().strip())
                    
                    # Check if the process is still running
                    if self._is_process_running(pid):
                        return False
                    
                    # Process is not running, remove stale lock
                    self.lock_file.unlink()
                except (ValueError, OSError):
                    # Invalid PID or file access error, remove lock file
                    self.lock_file.unlink(missing_ok=True)
            
            try:
                # Create lock file with current process ID
                self.lock_file_handle = open(self.lock_file, 'w')
                self.lock_file_handle.write(str(os.getpid()))
                self.lock_file_handle.flush()
                return True
            except OSError:
                return False
    
    def release(self):
        """Release the lock."""
        with self._lock:
            if self.lock_file_handle:
                self.lock_file_handle.close()
                self.lock_file_handle = None
            self.lock_file.unlink(missing_ok=True)
    
    def _is_process_running(self, pid):
        """Check if a process with given PID is running."""
        try:
            if sys.platform == "win32":
                # Windows
                from ctypes import windll
                handle = windll.kernel32.OpenProcess(1, False, pid)
                if handle == 0:
                    return False
                windll.kernel32.CloseHandle(handle)
                return True
            else:
                # Unix-like systems (Linux, macOS)
                os.kill(pid, 0)
                return True
        except (OSError, AttributeError):
            return False

class PlexLibraryExporter:
    SCRIPT_VERSION = "1.0.3"
    DEFAULT_PLEX_URL = "http://localhost:32400"
    DEFAULT_OUTPUT_DIR = "exports"
    PAGE_SIZE = 50
    
    def __init__(self):
        self.plex_url = self.DEFAULT_PLEX_URL
        self.plex_token = ""
        self.debug = False
        self.quiet = False
        self.force = False
        self.enable_logging = False
        
        # Setup directories
        self.log_dir = Path("logs")
        self.config_dir = Path("config")
        self.lock_file = Path(tempfile.gettempdir()) / "libretto.lock"
        self.lock = CrossPlatformLock(self.lock_file)
        
        # Setup logging
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"libretto-{self.timestamp}.log"
        self.error_log = self.log_dir / f"libretto-{self.timestamp}-error.log"
        
        # Setup HTTP session
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> ET.Element:
        headers = {
            "X-Plex-Token": self.plex_token,
            "Accept": "application/xml",
            "X-Plex-Client-Identifier": f"libretto-{self.SCRIPT_VERSION}",
            "X-Plex-Product": "Libretto (for Plex)",
            "X-Plex-Version": self.SCRIPT_VERSION
        }
        
        url = f"{self.plex_url}{endpoint}"
        response = self.session.get(url, headers=headers, params=params)
        response.raise_for_status()
        return ET.fromstring(response.content)

    def _get_paginated_results(self, endpoint: str) -> ET.Element:
        root = self._make_request(endpoint, {"X-Plex-Container-Start": 0, "X-Plex-Container-Size": 0})
        total_size = int(root.get('totalSize', 0))
        combined_root = ET.Element('MediaContainer')
        
        for start in range(0, total_size, self.PAGE_SIZE):
            if not self.quiet:
                current_page = (start // self.PAGE_SIZE) + 1
                total_pages = (total_size + self.PAGE_SIZE - 1) // self.PAGE_SIZE
                print(f"\r{Fore.CYAN}Fetching page {current_page}/{total_pages} ({self.PAGE_SIZE} items per page){Style.RESET_ALL}", 
                      end='', file=sys.stderr)
            
            params = {
                "X-Plex-Container-Start": start,
                "X-Plex-Container-Size": self.PAGE_SIZE
            }
            page_root = self._make_request(endpoint, params)
            
            for child in page_root:
                combined_root.append(child)
            
            time.sleep(0.5)
        
        if not self.quiet:
            print(f"\n{Fore.GREEN}Successfully retrieved all pages{Style.RESET_ALL}", file=sys.stderr)
        
        return combined_root

    def setup_logging(self):
        if not self.enable_logging:
            return

        self.log_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=logging.DEBUG if self.debug else logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

    def create_lock(self):
        """Create a cross-platform lock."""
        if not self.lock.acquire():
            print(f"{Fore.RED}Error: Another instance is running{Style.RESET_ALL}", file=sys.stderr)
            sys.exit(4)

    def remove_lock(self, _):
        """Remove the cross-platform lock."""
        self.lock.release()

    def get_libraries(self) -> List[Dict]:
        root = self._make_request("/library/sections")
        libraries = []
        
        for directory in root.findall(".//Directory"):
            libraries.append({
                'title': directory.get('title'),
                'key': directory.get('key'),
                'type': directory.get('type')
            })
        
        return libraries

    def format_duration(self, duration_ms: Optional[int]) -> str:
        if not duration_ms:
            return ""
        
        total_minutes = duration_ms // 60000
        hours = total_minutes // 60
        minutes = total_minutes % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def format_timestamp(self, timestamp: Optional[str]) -> str:
        if not timestamp:
            return ""
        return datetime.fromtimestamp(int(timestamp)).strftime("%Y-%m-%d %H:%M:%S")

    def process_text_field(self, text: Optional[str]) -> str:
        if not text:
            return ""
        text = html.unescape(text)
        text = unicodedata.normalize('NFC', text)
        return ' '.join(text.split())

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes == 0:
            return "0B"
        units = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
        i = 0
        while size_bytes >= 1024 and i < len(units) - 1:
            size_bytes /= 1024
            i += 1
        return f"{size_bytes:.1f}{units[i]}"

    def _get_movie_metadata(self, rating_key: str) -> Optional[str]:
        """Get full metadata for a specific movie including TMDB ID."""
        try:
            metadata = self._make_request(f"/library/metadata/{rating_key}")
            if self.debug:
                video = metadata.find('.//Video')
                if video is not None:
                    print(f"\nDEBUG: Full metadata for movie {rating_key}:")
                    for guid in video.findall('.//Guid'):
                        print(f"Found Guid: {guid.get('id')}")
            
            # Look for TMDB ID in Guid elements
            for guid in metadata.findall('.//Guid'):
                guid_id = guid.get('id', '')
                if 'tmdb://' in guid_id:
                    return guid_id.split('tmdb://')[-1]
            return ""
            
        except Exception as e:
            if self.debug:
                print(f"{Fore.YELLOW}Warning: Failed to get metadata for movie {rating_key}: {str(e)}{Style.RESET_ALL}")
            return ""

    def _get_show_metadata(self, rating_key: str) -> Optional[str]:
        """Get full metadata for a specific TV show including TMDB ID."""
        try:
            metadata = self._make_request(f"/library/metadata/{rating_key}")
            if self.debug:
                show = metadata.find('.//Directory')
                if show is not None:
                    print(f"\nDEBUG: Full metadata for show {rating_key}:")
                    for guid in show.findall('.//Guid'):
                        print(f"Found Guid: {guid.get('id')}")
            
            # Look for TMDB ID in Guid elements
            for guid in metadata.findall('.//Guid'):
                guid_id = guid.get('id', '')
                if 'tmdb://' in guid_id:
                    return guid_id.split('tmdb://')[-1]
            return ""
            
        except Exception as e:
            if self.debug:
                print(f"{Fore.YELLOW}Warning: Failed to get metadata for show {rating_key}: {str(e)}{Style.RESET_ALL}")
            return ""

    def export_movie_library(self, library_id: str, output_file: Path) -> Tuple[bool, int]:
        headers = [
            'title', 'year', 'tmdb_id', 'duration', 'studio', 'content_rating', 'summary',
            'rating', 'audience_rating', 'tagline', 'originally_available_at',
            'added_at', 'updated_at', 'video_resolution', 'audio_channels',
            'audio_codec', 'video_codec', 'container', 'video_frame_rate',
            'size', 'genres', 'countries', 'directors', 'writers', 'actors'
        ]
        
        items_exported = 0
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            
            root = self._get_paginated_results(f"/library/sections/{library_id}/all?type=1")
            total_items = len(root.findall(".//Video"))
            
            for i, video in enumerate(root.findall(".//Video"), 1):
                if not self.quiet:
                    print(f"\r{Fore.CYAN}Exporting movies: {i}/{total_items} ({(i/total_items)*100:.1f}%){Style.RESET_ALL}", 
                          end='', file=sys.stderr)
                
                rating_key = video.get('ratingKey')
                tmdb_id = self._get_movie_metadata(rating_key) if rating_key else ""
                
                media = video.find('.//Media')
                part = video.find('.//Media/Part')
                
                rating = video.get('rating')
                if rating:
                    rating = f"{float(rating) * 10:.0f}%"
                
                audience_rating = video.get('audienceRating')
                if audience_rating:
                    audience_rating = f"{float(audience_rating) * 10:.0f}%"
                
                genres = ' , '.join(g.get('tag', '') for g in video.findall('.//Genre'))
                countries = ' , '.join(c.get('tag', '') for c in video.findall('.//Country'))
                directors = ' , '.join(d.get('tag', '') for d in video.findall('.//Director'))
                writers = ' , '.join(w.get('tag', '') for w in video.findall('.//Writer'))
                actors = ' , '.join(a.get('tag', '') for a in video.findall('.//Role'))
                
                row = [
                    self.process_text_field(video.get('title')),
                    video.get('year', ''),
                    tmdb_id,
                    str(int(video.get('duration', 0)) // 60000),
                    self.process_text_field(video.get('studio')),
                    video.get('contentRating', ''),
                    self.process_text_field(video.get('summary')),
                    rating or '',
                    audience_rating or '',
                    self.process_text_field(video.get('tagline')),
                    video.get('originallyAvailableAt', ''),
                    self.format_timestamp(video.get('addedAt')),
                    self.format_timestamp(video.get('updatedAt')),
                    media.get('videoResolution', '') if media is not None else '',
                    media.get('audioChannels', '') if media is not None else '',
                    media.get('audioCodec', '') if media is not None else '',
                    media.get('videoCodec', '') if media is not None else '',
                    media.get('container', '') if media is not None else '',
                    media.get('videoFrameRate', '') if media is not None else '',
                    self._format_size(int(part.get('size', 0))) if part is not None else '',
                    genres,
                    countries,
                    directors,
                    writers,
                    actors
                ]
                writer.writerow(row)
                items_exported += 1
                
                time.sleep(0.1)
            
            if not self.quiet:
                print(f"\n{Fore.GREEN}Exported {items_exported} movies{Style.RESET_ALL}")
        
        return True, items_exported

    def export_tv_library(self, library_id: str, output_file: Path) -> Tuple[bool, int]:
        headers = [
            'series_title', 'tmdb_id', 'total_episodes', 'seasons', 'studio', 'content_rating',
            'summary', 'audience_rating', 'year', 'duration', 'originally_available_at',
            'added_at', 'updated_at', 'genres', 'countries', 'actors'
        ]
        
        items_exported = 0
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            
            root = self._get_paginated_results(f"/library/sections/{library_id}/all?type=2")
            total_items = len(root.findall(".//Directory"))
            
            for i, show in enumerate(root.findall(".//Directory"), 1):
                if not self.quiet:
                    print(f"\r{Fore.CYAN}Exporting TV shows: {i}/{total_items} ({(i/total_items)*100:.1f}%){Style.RESET_ALL}", 
                          end='', file=sys.stderr)
                
                rating_key = show.get('ratingKey')
                tmdb_id = self._get_show_metadata(rating_key) if rating_key else ""
                
                audience_rating = show.get('audienceRating')
                if audience_rating:
                    audience_rating = f"{float(audience_rating) * 10:.0f}%"
                
                genres = ' , '.join(g.get('tag', '') for g in show.findall('.//Genre'))
                countries = ' , '.join(c.get('tag', '') for c in show.findall('.//Country'))
                actors = ' , '.join(a.get('tag', '') for a in show.findall('.//Role'))
                
                row = [
                    self.process_text_field(show.get('title')),
                    tmdb_id,
                    show.get('leafCount', '0'),
                    show.get('childCount', '0'),
                    self.process_text_field(show.get('studio')),
                    show.get('contentRating', ''),
                    self.process_text_field(show.get('summary')),
                    audience_rating or '',
                    show.get('year', ''),
                    self.format_duration(int(show.get('duration', 0))),
                    show.get('originallyAvailableAt', ''),
                    self.format_timestamp(show.get('addedAt')),
                    self.format_timestamp(show.get('updatedAt')),
                    genres,
                    countries,
                    actors
                ]
                writer.writerow(row)
                items_exported += 1
                
                time.sleep(0.1)
            
            if not self.quiet:
                print(f"\n{Fore.GREEN}Exported {items_exported} TV shows{Style.RESET_ALL}")
        
        return True, items_exported

    def export_music_library(self, library_id: str, output_file: Path) -> Tuple[bool, int]:
        headers = [
            'artist', 'album', 'year', 'genres', 'studio',
            'added_at', 'updated_at'
        ]
        
        items_exported = 0
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
            writer.writerow(headers)
            
            root = self._get_paginated_results(f"/library/sections/{library_id}/all?type=9")
            total_items = len(root.findall(".//Directory"))
            
            for i, album in enumerate(root.findall(".//Directory"), 1):
                if not self.quiet:
                    print(f"\r{Fore.CYAN}Exporting albums: {i}/{total_items} ({(i/total_items)*100:.1f}%){Style.RESET_ALL}", 
                          end='', file=sys.stderr)
                
                genres = ' , '.join(g.get('tag', '') for g in album.findall('.//Genre'))
                
                row = [
                    self.process_text_field(album.get('parentTitle')),
                    self.process_text_field(album.get('title')),
                    album.get('year', ''),
                    genres,
                    self.process_text_field(album.get('studio')),
                    self.format_timestamp(album.get('addedAt')),
                    self.format_timestamp(album.get('updatedAt'))
                ]
                writer.writerow(row)
                items_exported += 1
            
            if not self.quiet:
                print(f"\n{Fore.GREEN}Exported {items_exported} albums{Style.RESET_ALL}")
        
        return True, items_exported

    def export_library(self, library_id: str, output_file: Path) -> Tuple[bool, int]:
        libraries = self.get_libraries()
        library_type = next((lib['type'] for lib in libraries if lib['key'] == library_id), None)
        
        if not library_type:
            print(f"{Fore.RED}Error: Could not determine type for library ID {library_id}{Style.RESET_ALL}", 
                  file=sys.stderr)
            return False, 0

        print(f"{Fore.CYAN}Exporting library ID {library_id} (type: {library_type}) to {output_file}{Style.RESET_ALL}")
        
        if output_file.exists() and not self.force:
            print(f"{Fore.RED}Error: Output file {output_file} already exists. Use -f to force overwrite.{Style.RESET_ALL}",
                  file=sys.stderr)
            return False, 0

        output_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            success = False
            items_exported = 0
            
            if library_type == "movie":
                success, items_exported = self.export_movie_library(library_id, output_file)
            elif library_type == "show":
                success, items_exported = self.export_tv_library(library_id, output_file)
            elif library_type == "artist":
                success, items_exported = self.export_music_library(library_id, output_file)
            else:
                print(f"{Fore.RED}Error: Unknown library type: '{library_type}' for library ID: {library_id}{Style.RESET_ALL}",
                      file=sys.stderr)
                return False, 0
            
            if success and items_exported > 0:
                print(f"{Fore.GREEN}Successfully exported {items_exported} items to {output_file}{Style.RESET_ALL}")
                if self.debug:
                    print(f"{Fore.YELLOW}First few lines of export:{Style.RESET_ALL}")
                    with open(output_file, 'r', encoding='utf-8') as f:
                        print(''.join(f.readlines()[:5]))
                return True, items_exported
            else:
                print(f"{Fore.YELLOW}Warning: No data was exported to {output_file}{Style.RESET_ALL}", 
                      file=sys.stderr)
                return False, 0
                
        except Exception as e:
            print(f"{Fore.RED}Error during export: {str(e)}{Style.RESET_ALL}", file=sys.stderr)
            if self.debug:
                import traceback
                traceback.print_exc()
            return False, 0

    def load_config(self):
        """Load configuration from config file"""
        config_file = self.config_dir / "libretto.conf"
        
        # Create default config if it doesn't exist
        if not config_file.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            default_config = f'''# Libretto (for Plex) Configuration File
# Location: config/libretto.conf

###################
# Server Settings #
###################

# Plex server URL (required)
PLEX_URL="{self.DEFAULT_PLEX_URL}"

# Your Plex authentication token (required)
# To find your token: https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
PLEX_TOKEN=""

###################
# Export Settings #
###################

# Default output directory for exports
OUTPUT_DIR="{self.DEFAULT_OUTPUT_DIR}"

# Force overwrite existing files (true/false)
FORCE=false

###################
# Debug Settings  #
###################

# Enable debug mode (true/false)
DEBUG=false

# Enable logging (true/false)
ENABLE_LOGGING=false

# Whether to run in quiet mode (true/false)
QUIET=false'''
            
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write(default_config)
            print(f"{Fore.GREEN}Created default configuration file: {config_file}{Style.RESET_ALL}")
            
        # Load config
        try:
            config = {}
            with open(config_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"')  # Remove quotes if present
                        config[key] = value

            self.plex_url = config.get("PLEX_URL", self.DEFAULT_PLEX_URL)
            self.plex_token = config.get("PLEX_TOKEN", "")
            self.force = config.get("FORCE", "false").lower() == "true"
            self.debug = config.get("DEBUG", "false").lower() == "true"
            self.enable_logging = config.get("ENABLE_LOGGING", "false").lower() == "true"
            self.quiet = config.get("QUIET", "false").lower() == "true"
        except Exception as e:
            print(f"{Fore.YELLOW}Warning: Could not read configuration file: {e}{Style.RESET_ALL}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description=f"{Style.BRIGHT}Libretto (for Plex) v{PlexLibraryExporter.SCRIPT_VERSION}{Style.RESET_ALL}",
        formatter_class=lambda prog: argparse.HelpFormatter(prog, max_help_position=27)) 
    
    parser.add_argument('-t', '--token', metavar='TOKEN',
                       help='Plex authentication token (required)')
    parser.add_argument('-u', '--url', metavar='URL',
                       help=f'Plex server URL (default: {PlexLibraryExporter.DEFAULT_PLEX_URL})')
    parser.add_argument('-l', '--list', action='store_true',
                       help='List all libraries')
    parser.add_argument('-n', '--name', metavar='NAME',
                       help='Export specific library by name')
    parser.add_argument('-o', '--output', metavar='FILE',
                       help='Output file')
    parser.add_argument('-d', '--dir', metavar='DIR',
                       help=f'Output directory (default: {PlexLibraryExporter.DEFAULT_OUTPUT_DIR})')
    parser.add_argument('-f', '--force', action='store_true',
                       help='Force overwrite of existing files')
    parser.add_argument('-q', '--quiet', action='store_true',
                       help='Quiet mode (no stdout output)')
    parser.add_argument('-v', '--debug', action='store_true',
                       help='Debug mode (verbose output)')
    parser.add_argument('--version', action='version',
                       version=f'{Style.BRIGHT}Libretto (for Plex) v{PlexLibraryExporter.SCRIPT_VERSION}{Style.RESET_ALL}')
    
    args = parser.parse_args()
    
    exporter = PlexLibraryExporter()
    exporter.load_config()
    
    # Override config with command line arguments
    if args.token:
        exporter.plex_token = args.token
    if args.url:
        exporter.plex_url = args.url
    if args.force:
        exporter.force = True
    if args.quiet:
        exporter.quiet = True
    if args.debug:
        exporter.debug = True
    
    # Validate required parameters
    if not exporter.plex_token:
        parser.error(f"{Fore.RED}Plex token is required. Use -t option.{Style.RESET_ALL}")
    
    # Setup logging and create lock
    exporter.setup_logging()
    lock_fd = exporter.create_lock()
    
    try:
        if args.list:
            # List libraries
            libraries = exporter.get_libraries()
            print(f"{Fore.CYAN}Available libraries:{Style.RESET_ALL}")
            for lib in libraries:
                print(f"  {Fore.GREEN}{lib['title']}{Style.RESET_ALL} (ID: {lib['key']}, Type: {lib['type']})")
            return 0
        
        # Set output file
        output_file = None
        if args.name:
            if args.output:
                output_file = Path(args.output)
            else:
                output_name = f"{args.name.replace(' ', '-')}.csv"
                if args.dir:
                    output_file = Path(args.dir) / output_name
                else:
                    output_file = Path(PlexLibraryExporter.DEFAULT_OUTPUT_DIR) / output_name
            
            # Find library ID by name
            libraries = exporter.get_libraries()
            library = next((lib for lib in libraries if lib['title'] == args.name), None)
            
            if not library:
                print(f"{Fore.RED}Error: Library '{args.name}' not found{Style.RESET_ALL}", file=sys.stderr)
                return 1
                
            success, items_exported = exporter.export_library(library['key'], output_file)
            return 0 if success else 1
        else:
            # Export all libraries
            export_dir = Path(args.dir or PlexLibraryExporter.DEFAULT_OUTPUT_DIR)
            export_dir.mkdir(parents=True, exist_ok=True)
            
            libraries = exporter.get_libraries()
            success_count = 0
            failure_count = 0
            skipped_count = 0
            total_items_exported = 0
            
            for i, library in enumerate(libraries, 1):
                print(f"\n{Fore.CYAN}Processing library {i}/{len(libraries)}: {library['title']}{Style.RESET_ALL}")
                output_file = export_dir / f"{library['title'].replace(' ', '-')}.csv"
                
                if output_file.exists() and not exporter.force:
                    print(f"{Fore.YELLOW}Skipping {library['title']}: Output file already exists. Use -f to force overwrite.{Style.RESET_ALL}")
                    skipped_count += 1
                    continue
                    
                success, items_exported = exporter.export_library(library['key'], output_file)
                if success:
                    success_count += 1
                    total_items_exported += items_exported
                else:
                    failure_count += 1
                    print(f"{Fore.RED}Failed to export {library['title']}, continuing with next library...{Style.RESET_ALL}")
            
            # Print summary
            print(f"\n{Fore.CYAN}Export Summary:{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}Successfully exported libraries: {success_count}{Style.RESET_ALL}")
            print(f"  {Fore.GREEN}Total items exported: {total_items_exported}{Style.RESET_ALL}")
            if failure_count > 0:
                print(f"  {Fore.RED}Failed to export: {failure_count}{Style.RESET_ALL}")
            if skipped_count > 0:
                print(f"  {Fore.YELLOW}Skipped (already exists): {skipped_count}{Style.RESET_ALL}")
            
            if success_count > 0:
                return 0
            else:
                print(f"{Fore.RED}Error: No libraries were successfully exported{Style.RESET_ALL}")
                return 1
    
    finally:
        exporter.remove_lock(lock_fd)


if __name__ == '__main__':
    sys.exit(main())
