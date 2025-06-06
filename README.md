# karaoke-telegram-bot

Telegram bot microservice for the Karaoke pipeline.

## Features

- Receives user requests
- Orchestrates download and submission into the main pipeline
- Shares volumes and network with pipeline stack

## Usage

1. Clone this repo
2. Copy `.env.example` to `.env` and fill in your Telegram credentials and settings.
3. Ensure external Docker volumes/networks exist and match those used in the main pipeline:

    ```bash
    docker volume create input
    docker volume create metadata
    docker volume create cookies
    docker network create backend
    ```

4. Start the bot:

    ```bash
    docker compose up -d
    ```

## Notes

- This service depends on the same external volumes as the pipeline.
- Can be deployed separately from the core pipeline.
