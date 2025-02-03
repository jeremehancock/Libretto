# Importer Scripts (for Libretto)

Python scripts for bulk importing movies and TV shows into Radarr and Sonarr using CSV files.

## Features

- Bulk import movies into Radarr from a CSV file
- Bulk import TV shows into Sonarr from a CSV file
- Cross-platform compatibility (Windows, macOS, Linux)
- Python 3.6+ compatibility
- Progress tracking with color-coded output
- Detailed import summaries
- Error handling with informative messages
- Duplicate detection to avoid adding existing content

## Requirements

- Python 3.6 or higher
- Radarr v3 or higher (for movie imports)
- Sonarr v3 or higher (for TV show imports)
- Valid API keys for your Radarr/Sonarr instances

### Dependencies

```
requests
colorama
```

## Installation

Follow steps in Libretto main [README](https://github.com/jeremehancock/Libretto?tab=readme-ov-file#installation)

## Configuration

### Radarr Script Configuration
Open `radarr-import.py` and modify the following variables at the top of the file:

```python
RADARR_URL = "http://localhost:7878"  # Change this to your Radarr URL
API_KEY = "your-api-key-here"         # Add your Radarr API key
ROOT_FOLDER_PATH = ""                 # Add your movies root folder path
```

### Sonarr Script Configuration
Open `sonarr-import.py` and modify the following variables at the top of the file:

```python
SONARR_URL = "http://localhost:8989"  # Change this to your Sonarr URL
API_KEY = "your-api-key-here"         # Add your Sonarr API key
ROOT_FOLDER_PATH = ""                 # Add your TV shows root folder path
```

## Generate CSV File(s)

Use Libretto to generate CSV Files. [See instructions](https://github.com/jeremehancock/Libretto?tab=readme-ov-file#basic-usage)

## Usage

### Importing Movies into Radarr
```bash
python radarr-import.py path/to/movies.csv
```

### Importing TV Shows into Sonarr
```bash
python sonarr-import.py path/to/shows.csv
```

## License

[MIT License](https://github.com/jeremehancock/Libretto/blob/main/LICENSE)

## AI Assistance Disclosure

This tool was developed with assistance from AI language models.