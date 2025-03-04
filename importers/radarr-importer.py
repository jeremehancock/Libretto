#!/usr/bin/env python3

# Radarr Importer (for Libretto)
# Import movies to Radarr from a CSV file created by Libretto
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

import sys
import csv
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional
from colorama import init, Fore, Style

# Initialize colorama for cross-platform color support
init()

# Configuration
RADARR_URL = "http://localhost:7878"  # Change this to your Radarr URL
API_KEY = ""                          # Add your Radarr API key here
ROOT_FOLDER_PATH = ""                 # Add your movies root folder path

class Movie:
    def __init__(self, title: str, year: str, tmdb_id: str) -> None:
        self.title = title
        self.year = year
        self.tmdb_id = tmdb_id

class ImportResults:
    def __init__(self):
        self.added_imports = []  # type: List[str]
        self.existing_imports = []  # type: List[str]
        self.failed_imports = []  # type: List[str]
        self.missing_ids = []  # type: List[str]
        self.error_details = []  # type: List[str]

class RadarrImporter:
    def __init__(self, url: str, api_key: str, root_folder: str):
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.root_folder = root_folder
        self.session = requests.Session()
        self.session.headers.update({'X-Api-Key': api_key})
        self.results = ImportResults()

    def check_movie_exists(self, tmdb_id: str) -> bool:
        response = self.session.get(f"{self.url}/api/v3/movie")
        response.raise_for_status()
        movies = response.json()
        return any(movie.get('tmdbId') == int(tmdb_id) for movie in movies)

    def add_movie(self, movie: Movie) -> bool:
        movie_entry = "{0} ({1})".format(movie.title, movie.year)

        # Check if movie already exists
        if self.check_movie_exists(movie.tmdb_id):
            self.results.existing_imports.append(movie_entry)
            return True

        # Get movie information from TMDb
        try:
            response = self.session.get(
                "{0}/api/v3/movie/lookup/tmdb".format(self.url),
                params={'tmdbId': movie.tmdb_id}
            )
            response.raise_for_status()
            movie_info = response.json()
            
            # Handle array response
            if isinstance(movie_info, list):
                if not movie_info:
                    raise ValueError("No movie found")
                movie_info = movie_info[0]

            # Add movie to Radarr
            movie_info.update({
                'qualityProfileId': 1,
                'rootFolderPath': self.root_folder,
                'monitored': True,
                'addOptions': {
                    'searchForMovie': True
                }
            })

            response = self.session.post(
                "{0}/api/v3/movie".format(self.url),
                json=movie_info
            )
            response.raise_for_status()
            
            self.results.added_imports.append(movie_entry)
            return True

        except Exception as e:
            self.results.failed_imports.append(movie_entry)
            self.results.error_details.append("{0} - Error: {1}".format(movie_entry, str(e)))
            return False

def show_progress(current: int, total: int):
    percentage = (current * 100) // total
    print("\r{0}Progress: {1:3d}% ({2}/{3}){4}".format(
        Fore.CYAN, percentage, current, total, Style.RESET_ALL
    ), end='')
    sys.stdout.flush()

def print_summary(results: ImportResults):
    print("\n{0}----------------------------------------{1}".format(Fore.BLUE, Style.RESET_ALL))
    print("{0}Import Summary{1}".format(Style.BRIGHT, Style.RESET_ALL))
    print("{0}----------------------------------------{1}".format(Fore.BLUE, Style.RESET_ALL))
    
    print("{0}Successfully added: {1} movies{2}".format(
        Fore.GREEN, len(results.added_imports), Style.RESET_ALL))
    
    if results.existing_imports:
        print("{0}Already in Radarr: {1} movies{2}".format(
            Fore.YELLOW, len(results.existing_imports), Style.RESET_ALL))
    
    if results.failed_imports:
        print("{0}Failed to import: {1} movies{2}".format(
            Fore.RED, len(results.failed_imports), Style.RESET_ALL))
    
    if results.missing_ids:
        print("{0}Missing TMDb IDs: {1} movies{2}".format(
            Fore.YELLOW, len(results.missing_ids), Style.RESET_ALL))

    # Print details
    if results.existing_imports:
        print("\n{0}Already in Radarr:{1}".format(Style.BRIGHT, Style.RESET_ALL))
        for movie in results.existing_imports:
            print("  {0}".format(movie))

    if results.error_details:
        print("\n{0}Failed Imports:{1}".format(Style.BRIGHT, Style.RESET_ALL))
        for error in results.error_details:
            print("  {0}".format(error))

    if results.missing_ids:
        print("\n{0}Movies Missing TMDb IDs:{1}".format(Style.BRIGHT, Style.RESET_ALL))
        for movie in results.missing_ids:
            print("  {0}".format(movie))

def main():
    if len(sys.argv) != 2:
        print("{0}Usage: {1} <csv_file>{2}".format(Fore.RED, sys.argv[0], Style.RESET_ALL))
        sys.exit(1)

    if not API_KEY:
        print("{0}Please set your Radarr API key in the script{1}".format(
            Fore.RED, Style.RESET_ALL))
        sys.exit(1)

    if not ROOT_FOLDER_PATH:
        print("{0}Please set your root folder path in the script{1}".format(
            Fore.RED, Style.RESET_ALL))
        sys.exit(1)

    csv_file = Path(sys.argv[1])
    if not csv_file.exists():
        print("{0}CSV file not found: {1}{2}".format(
            Fore.RED, csv_file, Style.RESET_ALL))
        sys.exit(1)

    importer = RadarrImporter(RADARR_URL, API_KEY, ROOT_FOLDER_PATH)
    
    print("\n{0}Starting Radarr Import Process{1}".format(Style.BRIGHT, Style.RESET_ALL))
    print("{0}----------------------------------------{1}".format(Fore.BLUE, Style.RESET_ALL))

    try:
        with open(str(csv_file), 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            total_movies = len(rows)
            
            for i, row in enumerate(rows, 1):
                show_progress(i, total_movies)
                
                movie = Movie(
                    title=row['title'].strip(),
                    year=row['year'].strip(),
                    tmdb_id=row['tmdb_id'].strip()
                )
                
                if movie.tmdb_id:
                    importer.add_movie(movie)
                else:
                    importer.results.missing_ids.append("{0} ({1})".format(
                        movie.title, movie.year))

    except Exception as e:
        print("\n{0}Error processing CSV file: {1}{2}".format(
            Fore.RED, str(e), Style.RESET_ALL))
        sys.exit(1)

    print("\r" + " " * 80)  # Clear progress line
    print_summary(importer.results)
    print("\n{0}----------------------------------------{1}".format(Fore.BLUE, Style.RESET_ALL))
    print("{0}Import process completed{1}".format(Style.BRIGHT, Style.RESET_ALL))

if __name__ == "__main__":
    main()
