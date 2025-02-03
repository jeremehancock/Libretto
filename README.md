# Libretto (for Plex)

Libretto is a powerful Python tool that exports detailed information from your Plex Media Server libraries into CSV format. It supports movies, TV shows, and music libraries with rich metadata extraction.

## Features

- Export complete library metadata to CSV files
- Support for Movies, TV Shows, and Music libraries
- Detailed metadata including titles, ratings, release dates, technical specifications, and more
- Paginated data retrieval to handle large libraries efficiently
- Configurable output locations
- Progress tracking with colorful console output
- Robust error handling and logging

## Requirements

- Python 3.6 or higher
- A Plex Media Server
- Plex authentication token

### Dependencies

```
requests
urllib3
colorama
```

## Installation

1. Clone the repository:
```bash
git clone git@github.com:jeremehancock/Libretto.git
```

2. Change directory:
```bash
cd Libretto
```

3. Install required packages:
```bash
pip install -r requirements.txt
```

## Configuration

Libretto can be configured either through command-line arguments or a configuration file. On first run, a default configuration file will be created at `config/libretto.conf`.

### Configuration File
```ini
# Libretto (for Plex) Configuration File
# Location: config/libretto.conf

###################
# Server Settings #
###################

# Plex server URL (required)
PLEX_URL="http://localhost:32400"

# Your Plex authentication token (required)
# To find your token: https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/
PLEX_TOKEN=""

###################
# Export Settings #
###################

# Default output directory for exports
OUTPUT_DIR="exports"

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
QUIET=false
```

You can modify these settings by editing the file directly or override them using command-line options.

## Usage

### Basic Usage

If you haven't set your Plex token in the config file:
```bash
./libretto.py -t YOUR_PLEX_TOKEN [options]
```

If you've already set your Plex token in the config file:
```bash
./libretto.py [options]
```

### Command Line Options

```
-t, --token TOKEN    Plex authentication token (required)
-u, --url URL        Plex server URL (default: http://localhost:32400)
-l, --list           List all libraries
-n, --name NAME      Export specific library by name
-o, --output FILE    Output file
-d, --dir DIR        Output directory (default: exports)
-f, --force          Force overwrite of existing files
-q, --quiet          Quiet mode (no stdout output)
-v, --debug          Debug mode (verbose output)
--version            Show version information
```

## Export Format

### Movies
The movie export includes:
- Basic information (title, year, duration)
- Technical details (resolution, audio/video codecs)
- Metadata (ratings, genres, cast, crew)
- File information (size, container format)
- Timestamps (added, updated)

### TV Shows
The TV show export includes:
- Series information (title, episodes, seasons)
- Metadata (ratings, genres, cast)
- Air dates and availability
- Production details (studio, content rating)

### Music
The music export includes:
- Artist and album information
- Release year
- Genres
- Studio/Label
- Added/Updated timestamps

## Development

### Project Structure
```
libretto/
├── libretto.py        # Main script
├── config/            # Configuration files
│   └── libretto.conf
├── exports/           # Default export directory
├── logs/              # Log files
└── requirements.txt   # Requirements file
```

### Error Handling

Libretto includes comprehensive error handling:
- File system permission checks
- Network connectivity issues
- Invalid authentication
- Malformed responses
- Concurrent execution prevention

## Importers

Libretto includes imports for Radarr and Sonarr. Check them out [here](https://github.com/jeremehancock/Libretto/tree/main/importers#importer-scripts-for-libretto).

## License

[MIT License](LICENSE)

## AI Assistance Disclosure

This tool was developed with assistance from AI language models.